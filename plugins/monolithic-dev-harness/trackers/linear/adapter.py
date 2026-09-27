"""Linear through its hosted MCP server (`mcp-remote https://mcp.linear.app/mcp`).

Issues are addressed by their identifier (`ENG-12`). The harness work kind travels as an issue
label named in the manifest's `kinds`; artifacts and development links are issue comments.
A sprint is a cycle: Linear knows its dates and each issue's point estimate, but no team capacity
and no hours, so planning reports that and names no hour fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.result import Ok, Result, bind, err, fmap
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
from integrations.planning import (
    EstimableItem,
    IterationCapacity,
    IterationReading,
    first_number,
    parse_date,
)

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
        read_iteration=lambda replies, ref: Ok(_cycle(replies.get("cycle"), ref)),
        iteration_items=lambda replies, ref: Ok(
            tuple(
                _estimable(context, record)
                for record in payloads.records(replies.get("issues"))
                if payloads.text(record, "identifier", "id")
            )
        ),
        hour_fields=lambda hours, first: EMPTY,
    )


def _caller(context: AdapterContext):
    tools = context.manifest.tools
    return lambda tool, arguments: context.call(tools[tool], arguments)


def _issue(context: AdapterContext, reply: Any) -> Result[WorkItem]:
    record = reply.get("issue", reply) if isinstance(reply, dict) else None
    return (
        Ok(work_item(context, record))
        if isinstance(record, dict) and payloads.text(record, "identifier", "id")
        else err("provider_error", "Linear did not return an issue")
    )


def _issues(context: AdapterContext, reply: Any) -> tuple[WorkItem, ...]:
    return tuple(work_item(context, record) for record in payloads.records(reply))


def _cursor(reply: Any) -> str:
    page = reply.get("pageInfo", {}) if isinstance(reply, dict) else {}
    return (
        payloads.text(reply, "nextCursor", "cursor") if isinstance(reply, dict) else ""
    ) or (payloads.text(page, "endCursor") if page.get("hasNextPage") else "")


def work_item(context: AdapterContext, record: Mapping[str, Any]) -> WorkItem:
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


def _cycle(reply: Any, iteration_ref: str) -> IterationReading:
    """A cycle's dates, from one cycle or a listing whose first entry is the one asked for."""
    cycle = (
        reply
        if isinstance(reply, dict) and ("startsAt" in reply or "endsAt" in reply)
        else next(iter(payloads.records(reply)), EMPTY)
    )
    return IterationReading(
        IterationCapacity(
            iteration_ref=iteration_ref,
            start_date=parse_date(cycle.get("startsAt")),
            finish_date=parse_date(cycle.get("endsAt")),
        ),
        (NO_CAPACITY,),
    )


def _estimable(context: AdapterContext, record: Mapping[str, Any]) -> EstimableItem:
    item = work_item(context, record)
    person = payloads.object_or_empty(record.get("assignee"))
    cycle = payloads.object_or_empty(record.get("cycle"))
    return EstimableItem(
        item_id=item.id,
        title=item.title,
        item_type=item.kind.value,
        points=first_number(record, "estimate"),
        assigned_to=payloads.text(person, "displayName", "name")
        or payloads.text(record, "assignee")
        or None,
        state=_name(record.get("state") or record.get("status")),
        iteration=payloads.text(cycle, "name", "number") or None,
    )
