"""Linear through its hosted MCP server (`mcp-remote https://mcp.linear.app/mcp`).

Issues are addressed by their identifier (`ENG-12`). The harness work kind travels as an issue
label named in the manifest's `kinds`; artifacts and development links are issue comments.
A sprint is a cycle: Linear knows its dates and each issue's point estimate, but no team capacity
and no hours, so planning reports that and names no hour fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from core.result import Ok, Result, bind, err, fmap, require
from integrations import artifacts, payloads
from integrations.contracts import (
    EMPTY,
    AdapterContext,
    LogicalState,
    Page,
    TrackerOps,
    WorkItem,
    WorkItemKind,
)
from integrations.payloads import as_float, first_number, parse_date
from integrations.planning import (
    EstimableItem,
    IterationCapacity,
    IterationReading,
    no_hours,
    pick_sprint,
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
        link_development_artifact=lambda ref, url, kind: fmap(
            call("comment", {"issueId": ref.upper(), "body": f"{kind}: {url}"}),
            payloads.mapping,
        ),
        read_iteration=lambda replies, ref: fmap(
            _usable(replies, "cycle", CYCLE_MARKERS),
            lambda _: _cycle(replies.get("cycle"), ref),
        ),
        iteration_items=lambda replies, ref: fmap(
            _usable(replies, "issues", ("identifier",)),
            lambda _: tuple(
                _estimable(context, record)
                for record in payloads.records(replies.get("issues"))
                if payloads.text(record, "identifier", "id")
            ),
        ),
        hour_fields=no_hours,
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
        provider_data=record,
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


def _usable(
    replies: Mapping[str, Any], key: str, markers: tuple[str, ...]
) -> Result[None]:
    """A reply that was fetched but holds no data (an error text, say) is refused, not read as
    an empty cycle."""
    return require(
        key not in replies or payloads.readable(replies[key], *markers),
        "unreadable_reply",
        f"the {key} reply holds no usable data, fetch it again",
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


def _active(cycles: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any] | None:
    """The cycle Linear marks active, else the one running today."""
    today = datetime.now(timezone.utc).date()
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
