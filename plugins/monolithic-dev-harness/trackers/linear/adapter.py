"""Linear through its hosted MCP server (`mcp-remote https://mcp.linear.app/mcp`).

Issues are addressed by their identifier (`ENG-12`). The harness work kind travels as an issue
label named in the manifest's `kinds`; artifacts and development links are issue comments.
A sprint is a cycle: Linear knows its dates and each issue's point estimate, but no team capacity
and no hours, so planning reports that and names no hour fields.

The `save_issue` arguments for parent (`parentId`), labels and priority follow the hosted server's
documented tool names; their exact shapes are confirmed only by a Linear trial.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from core.result import Ok, Result, bind, err, fmap
from integrations import artifacts, payloads
from integrations.contracts import (
    EMPTY,
    AdapterContext,
    FieldNames,
    LogicalState,
    Page,
    TrackerOps,
    WorkItem,
    WorkItemChanges,
    WorkItemKind,
    changed_fields,
)
from integrations.payloads import as_float, first_number, parse_date
from integrations.planning import (
    EstimableItem,
    IterationCapacity,
    IterationReading,
    Sprint,
    is_current,
    no_hours,
    pick_sprint,
)

FIELDS = FieldNames(
    "title", "description", "estimate", "assignee", "cycle", "labels", "priority"
)
CYCLE_MARKERS = ("startsAt", "endsAt")  # a single cycle, not a listing
NO_CAPACITY = (
    "Linear records no team capacity; only the cycle's dates are known, so availability is "
    "not checked"
)


def adapter(context: AdapterContext) -> TrackerOps:
    call = _caller(context)
    issue = lambda reply: _issue(context, reply)  # noqa: E731 - a named one-liner reads better here
    return TrackerOps(
        get_work_item=lambda ref: bind(call("get", {"id": ref.upper()}), issue),
        search_work_items=lambda query, cursor: fmap(
            call("list", {"query": query, **({"cursor": cursor} if cursor else {})}),
            lambda reply: Page(_issues(context, reply), _cursor(reply)),
        ),
        create_work_item=lambda kind, title, description, parent: bind(
            call(
                "save",
                {
                    "title": title,
                    "description": description,
                    "team": context.values.get("team", ""),
                    "labels": [context.manifest.kinds[kind]],
                    **({"parentId": parent.upper()} if parent else {}),
                },
            ),
            issue,
        ),
        update_work_item=lambda ref, changes: bind(
            changed_fields(changes, FIELDS, no_hours),
            lambda fields: bind(
                _existing_parent(call, context, changes.parent),
                lambda _: bind(
                    _with_kind_label(call, context, ref, fields),
                    lambda fields: bind(
                        call(
                            "save",
                            {"id": ref.upper(), **fields, **_parent_field(changes)},
                        ),
                        issue,
                    ),
                ),
            ),
        ),
        transition_work_item=lambda ref, state: bind(
            call("save", {"id": ref.upper(), "state": context.manifest.states[state]}),
            issue,
        ),
        list_children=lambda ref: fmap(
            call("list", {"parentId": ref.upper()}),
            lambda reply: tuple(
                item
                for item in _issues(context, reply)
                if item.parent_id.upper() == ref.upper()
            ),
        ),
        list_artifacts=lambda ref: fmap(
            call("comments", {"issueId": ref.upper()}),
            lambda reply: artifacts.references(
                payloads.records(reply), "body", "content"
            ),
        ),
        add_artifact=lambda ref, draft: fmap(
            call("comment", {"issueId": ref.upper(), "body": artifacts.encode(draft)}),
            lambda reply: artifacts.added(_comment(reply), draft),
        ),
        revise_artifact=lambda ref, artifact, draft: fmap(
            call("comment", {"id": artifact.id, "body": artifacts.encode(draft)}),
            lambda reply: artifacts.added(_comment(reply), draft),
        ),
        link_development_artifact=lambda ref, url, kind: fmap(
            call("comment", {"issueId": ref.upper(), "body": f"{kind}: {url}"}),
            payloads.mapping,
        ),
        current_sprint=lambda: fmap(_cycle_entry(context, call, ""), _sprint),
        sprint_capacity=lambda ref: fmap(
            _cycle_listing(context, call, ref),
            lambda listing: _cycle(_pick(listing, ref) or listing, ref),
        ),
        sprint_items=lambda ref: bind(
            _cycle_listing(context, call, ref),
            lambda listing: _cycle_items(context, call, _pick(listing, ref)),
        ),
        records_hours=False,
        optional={
            "remove_artifact": lambda ref, artifact: fmap(
                call("comment_delete", {"id": artifact.id}), lambda _: None
            ),
        },
    )


def _caller(context: AdapterContext):
    tools = context.manifest.tools
    return lambda tool, arguments: context.call(tools[tool], arguments)


def _issue(context: AdapterContext, reply: Any) -> Result[WorkItem]:
    record = reply.get("issue", reply) if isinstance(reply, dict) else None
    return (
        Ok(_item(context, record))
        if isinstance(record, dict) and payloads.text(record, "identifier", "id")
        else err("provider_error", "Linear did not return an issue")
    )


def _issues(context: AdapterContext, reply: Any) -> tuple[WorkItem, ...]:
    return tuple(_item(context, record) for record in payloads.records(reply))


def _cursor(reply: Any) -> str:
    page = reply.get("pageInfo", {}) if isinstance(reply, dict) else {}
    return (
        payloads.text(reply, "nextCursor", "cursor") if isinstance(reply, dict) else ""
    ) or (payloads.text(page, "endCursor") if page.get("hasNextPage") else "")


def _item(context: AdapterContext, record: Mapping[str, Any]) -> WorkItem:
    manifest = context.manifest
    identifier = payloads.text(record, "identifier", "id")
    return WorkItem(
        id=identifier,
        key=identifier,
        title=payloads.text(record, "title"),
        kind=_kind(manifest.kinds, _names(record.get("labels"))),
        state=payloads.reverse(
            manifest.states,
            _name(record.get("state") or record.get("status")),
            LogicalState.BACKLOG,
        ),
        url=payloads.text(record, "url"),
        description=payloads.text(record, "description"),
        parent_id=_parent(record),
        tags=tuple(
            label
            for label in _names(record.get("labels"))
            if payloads.normalized(label)
            not in {payloads.normalized(name) for name in manifest.kinds.values()}
        ),
        priority=_priority(record.get("priority")),
        provider_data=record,
    )


def _priority(value: Any) -> int | None:
    """Linear's 1 (urgent) … 4 (low); its 0 means no priority."""
    number = payloads.text(value, "value") if isinstance(value, dict) else value
    return int(number) if str(number or "").isdigit() and int(number) > 0 else None


def _parent_field(changes: WorkItemChanges) -> dict[str, str]:
    return {"parentId": changes.parent.upper()} if changes.parent else {}


def _existing_parent(call, context: AdapterContext, parent: str | None) -> Result[None]:
    """A new parent that Linear holds; a move under one it does not changes nothing."""
    if not parent:
        return Ok(None)
    return fmap(
        bind(call("get", {"id": parent.upper()}), lambda reply: _issue(context, reply)),
        lambda _: None,
    )


def _with_kind_label(
    call, context: AdapterContext, ref: str, fields: dict[str, Any]
) -> Result[dict[str, Any]]:
    """The fields with the issue's own work-kind label added to a new tag list: the kind travels
    as a label, so replacing the labels must keep it."""
    if "labels" not in fields:
        return Ok(fields)
    return bind(
        bind(call("get", {"id": ref.upper()}), lambda reply: _issue(context, reply)),
        lambda item: Ok(
            {**fields, "labels": [*fields["labels"], context.manifest.kinds[item.kind]]}
        ),
    )


def _name(value: Any) -> str:
    return payloads.text(value, "name") if isinstance(value, dict) else str(value or "")


def _names(labels: Any) -> tuple[str, ...]:
    return tuple(
        map(_name, payloads.items(labels) if not isinstance(labels, list) else labels)
    )


def _kind(kinds: Mapping[WorkItemKind, str], labels: tuple[str, ...]) -> WorkItemKind:
    wanted = {payloads.normalized(label) for label in labels}
    return next(
        (kind for kind, name in kinds.items() if payloads.normalized(name) in wanted),
        WorkItemKind.TASK,
    )


def _parent(record: Mapping[str, Any]) -> str:
    parent = record.get("parent")
    return (
        payloads.text(parent, "identifier", "id") if isinstance(parent, dict) else ""
    ) or payloads.text(record, "parentId")


def _comment(reply: Any) -> Mapping[str, Any]:
    return payloads.mapping(
        reply.get("comment", reply) if isinstance(reply, dict) else reply
    )


def _cycle(reply: Any, iteration_ref: str) -> IterationReading:
    """A cycle's dates; see `pick_sprint`. Linear records no team capacity, and says so."""
    cycle, missing = pick_sprint(
        reply, iteration_ref, CYCLE_MARKERS, ("id", "name", "number"), _active
    )
    return IterationReading(
        IterationCapacity(
            iteration_ref=iteration_ref,
            start_date=parse_date((cycle or EMPTY).get("startsAt")),
            finish_date=parse_date((cycle or EMPTY).get("endsAt")),
        ),
        (NO_CAPACITY, *missing),
    )


def _cycle_listing(context: AdapterContext, call, ref: str) -> Result[Any]:
    """The team's cycles: only the current one when `ref` asks for it."""
    team = context.values.get("team", "")
    return bind(
        call(
            "cycles",
            {"teamId": team, **({"type": "current"} if is_current(ref) else {})},
        ),
        lambda reply: _readable(reply, "cycles", CYCLE_MARKERS),
    )


def _readable(reply: Any, what: str, markers: tuple[str, ...]) -> Result[Any]:
    """A reply that holds data; error text in its place is refused, never read as "none"."""
    return (
        Ok(reply)
        if payloads.readable(reply, *markers)
        else err("unreadable_reply", f"Linear returned no usable data for the {what}")
    )


def _pick(listing: Any, ref: str) -> Mapping[str, Any] | None:
    return pick_sprint(listing, ref, CYCLE_MARKERS, ("id", "name", "number"), _active)[
        0
    ]


def _cycle_entry(context: AdapterContext, call, ref: str) -> Result[Mapping[str, Any]]:
    """The team's cycle `ref` names (id, name or number), or the current one."""
    current = is_current(ref)
    return bind(
        _cycle_listing(context, call, ref),
        lambda listing: _found(
            _pick(listing, ref),
            "the team has no current cycle"
            if current
            else f"the team has no cycle {ref!r}",
            "no_current_sprint" if current else "sprint_not_found",
        ),
    )


def _cycle_items(
    context: AdapterContext, call, cycle: Mapping[str, Any] | None
) -> Result[tuple[EstimableItem, ...]]:
    """The cycle's issues; a cycle the team does not have holds none."""
    if cycle is None:
        return Ok(())
    return fmap(
        bind(
            call(
                "list",
                {
                    "team": context.values.get("team", ""),
                    "cycle": payloads.text(cycle, "id"),
                },
            ),
            lambda reply: _readable(reply, "cycle's issues", ("identifier",)),
        ),
        lambda reply: tuple(
            _estimable(context, record)
            for record in payloads.records(reply)
            if payloads.text(record, "identifier", "id")
        ),
    )


def _found(
    cycle: Mapping[str, Any] | None, missing: str, code: str
) -> Result[Mapping[str, Any]]:
    return Ok(cycle) if cycle is not None else err(code, missing)


def _sprint(cycle: Mapping[str, Any]) -> Sprint:
    """A cycle as a sprint; an issue joins it by the cycle's id."""
    cycle_id = payloads.text(cycle, "id")
    return Sprint(
        id=cycle_id,
        name=payloads.text(cycle, "name") or f"Cycle {payloads.text(cycle, 'number')}",
        path=cycle_id,
        start=parse_date(cycle.get("startsAt")),
        end=parse_date(cycle.get("endsAt")),
    )


def _active(cycles: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any] | None:
    """The cycle Linear marks active, else the one running today."""
    today = datetime.now(UTC).date()
    return next(
        (cycle for cycle in cycles if cycle.get("isActive") is True),
        next(
            (
                cycle
                for cycle in cycles
                if (start := parse_date(cycle.get("startsAt"))) is not None
                and (end := parse_date(cycle.get("endsAt"))) is not None
                and start <= today <= end
            ),
            None,
        ),
    )


def _estimable(context: AdapterContext, record: Mapping[str, Any]) -> EstimableItem:
    item = _item(context, record)
    person = record.get("assignee")
    estimate = record.get("estimate")
    return EstimableItem(
        item_id=item.id,
        title=item.title,
        item_type=item.kind.value,
        points=as_float(estimate)
        if not isinstance(estimate, dict)
        else first_number(estimate, "value"),
        assigned_to=(
            payloads.text(person, "displayName", "name")
            if isinstance(person, dict)
            else str(person or "")
        )
        or None,
        state=_name(record.get("state") or record.get("status")),
        iteration=payloads.text(
            payloads.object_or_empty(record.get("cycle")), "name", "number"
        )
        or None,
    )
