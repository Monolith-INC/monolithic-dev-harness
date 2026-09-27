"""Azure Boards through the `@azure-devops/mcp` server.

The server has one tool per area and an `action` argument per operation (`wit_query` + `wiql`,
`wit_work_item_write` + `create`, ...); every call names the project. Work items come back in the
REST shape (`id`, `fields["System.Title"]`, ...), sometimes as JSON text in a `body` field.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, sequence, value_or
from integrations import artifacts, payloads
from integrations.contracts import (
    AdapterContext,
    ArtifactDraft,
    ArtifactRef,
    LogicalState,
    Page,
    TrackerOps,
    WorkItem,
    WorkItemKind,
)

FIELDS = (
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.State",
    "System.Description",
    "System.Parent",
)
LIMIT = (
    200  # the server's cap on one WIQL result, one batch read, and one page of comments
)
# A WIQL condition names a field (`[System.State]`, `[Custom.Team]`); anything else is search text.
WIQL_FIELD = re.compile(r"\[[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+\]")


def adapter(context: AdapterContext) -> TrackerOps:
    call = _caller(context)
    read = _reader(context, call)
    return TrackerOps(
        get_work_item=read,
        search_work_items=lambda query, cursor: _search(context, call, query),
        create_work_item=lambda kind, title, description, parent: _create(
            context, call, read, kind, title, description, parent
        ),
        transition_work_item=lambda ref, state: _transition(
            context, call, read, ref, state
        ),
        list_children=lambda ref: bind(
            payloads.number(ref, "parent"),
            lambda parent: _query(
                context,
                call,
                f"SELECT [System.Id] FROM WorkItems WHERE [System.Parent] = {parent}",
            ),
        ),
        list_artifacts=lambda ref: _comments(call, ref),
        add_artifact=lambda ref, draft: _comment(call, ref, draft),
        link_development_artifact=lambda ref, url, kind: bind(
            payloads.number(ref, "work item"),
            lambda number: fmap(
                call(
                    "link",
                    "link",
                    {
                        "updates": [
                            {
                                "id": number,
                                "type": "hyperlink",
                                "url": url,
                                "comment": kind,
                            }
                        ]
                    },
                ),
                payloads.mapping,
            ),
        ),
    )


def _caller(context: AdapterContext):
    project = context.values.get("project", "")
    tools = context.manifest.tools

    def call(tool: str, action: str, arguments: Mapping[str, Any]) -> Result[Any]:
        present = {key: value for key, value in arguments.items() if value is not None}
        return context.call(
            tools[tool], {"action": action, "project": project, **present}
        )

    return call


def _reader(context: AdapterContext, call):
    def read(ref: str) -> Result[WorkItem]:
        return bind(
            payloads.number(ref, "work item"),
            lambda number: bind(
                call("read", "get", {"id": number, "expand": "Relations"}),
                lambda reply: _first(
                    context, reply, f"work item {ref} was not returned"
                ),
            ),
        )

    return read


def _first(context: AdapterContext, reply: Any, missing: str) -> Result[WorkItem]:
    match _records(reply):
        case (record, *_):
            return Ok(work_item(context, record))
        case ():
            return err("not_found", missing)


def _records(reply: Any) -> tuple[Mapping[str, Any], ...]:
    """Work item records from one record, a wrapped list, or a batch whose items carry JSON text."""
    candidates = (
        (reply,)
        if isinstance(reply, dict) and ("fields" in reply or "id" in reply)
        else payloads.items(reply)
    )
    return tuple(
        record for record in map(_unwrapped, candidates) if isinstance(record, dict)
    )


def _unwrapped(item: Any) -> Any:
    match item:
        case {"body": str(body)}:
            return value_or(
                attempt(lambda: json.loads(body), "bad_body", "batch item", ValueError),
                None,
            )
        case _:
            return item


def work_item(context: AdapterContext, record: Mapping[str, Any]) -> WorkItem:
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    link = ((record.get("_links") or {}).get("html") or {}).get("href")
    manifest = context.manifest
    return WorkItem(
        id=payloads.text(record, "id") or payloads.text(fields, "System.Id"),
        key=payloads.text(record, "id") or payloads.text(fields, "System.Id"),
        title=payloads.text(fields, "System.Title"),
        kind=payloads.reverse(
            manifest.kinds,
            payloads.text(fields, "System.WorkItemType"),
            WorkItemKind.TASK,
        ),
        state=payloads.reverse(
            manifest.states, payloads.text(fields, "System.State"), LogicalState.BACKLOG
        ),
        url=str(link or record.get("url") or ""),
        description=payloads.text(fields, "System.Description"),
        parent_id=payloads.text(fields, "System.Parent"),
        provider_data=record,
    )


def wiql(query: str) -> str:
    """A WIQL statement from a statement, a condition naming a field, or plain search text."""
    text = query.strip()
    condition = (
        text
        if WIQL_FIELD.search(text)
        else "[System.Title] CONTAINS '{}'".format(text.replace("'", "''"))
    )
    return (
        text
        if text.upper().startswith("SELECT")
        else "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "
        f"AND ({condition}) ORDER BY [System.ChangedDate] DESC"
    )


def _ids(call, statement: str) -> Result[tuple[int, ...]]:
    return fmap(
        call("query", "wiql", {"wiql": statement, "top": LIMIT}),
        lambda reply: tuple(
            int(item["id"])
            for item in payloads.records(reply)
            if str(item.get("id", "")).isdigit()
        ),
    )


def _batch(
    context: AdapterContext, call, ids: tuple[int, ...]
) -> Result[tuple[WorkItem, ...]]:
    chunks = tuple(ids[start : start + LIMIT] for start in range(0, len(ids), LIMIT))
    return fmap(
        sequence(
            call("read", "get_batch", {"ids": list(chunk), "fields": list(FIELDS)})
            for chunk in chunks
        ),
        lambda replies: tuple(
            work_item(context, record)
            for reply in replies
            for record in _records(reply)
        ),
    )


def _query(
    context: AdapterContext, call, statement: str
) -> Result[tuple[WorkItem, ...]]:
    return bind(_ids(call, statement), lambda ids: _batch(context, call, ids))


def _search(context: AdapterContext, call, query: str) -> Result[Page]:
    # The server caps a WIQL result; say so rather than implying the result is complete.
    return bind(
        _ids(call, wiql(query)),
        lambda ids: fmap(
            _batch(context, call, ids), lambda found: Page(found, "", len(ids) >= LIMIT)
        ),
    )


def _create(
    context: AdapterContext,
    call,
    read,
    kind: WorkItemKind,
    title: str,
    description: str,
    parent: str,
) -> Result[WorkItem]:
    work_type = context.manifest.kinds[kind]
    request = (
        bind(
            payloads.number(parent, "parent"),
            lambda number: call(
                "write",
                "add_child",
                {
                    "parentId": number,
                    "workItemType": work_type,
                    "items": [
                        {
                            "title": title,
                            "description": description,
                            "format": "Markdown",
                        }
                    ],
                },
            ),
        )
        if parent
        else call(
            "write",
            "create",
            {
                "workItemType": work_type,
                "fields": [
                    {"name": "System.Title", "value": title},
                    {
                        "name": "System.Description",
                        "value": description,
                        "format": "Markdown",
                    },
                ],
            },
        )
    )
    # Read it back so the caller gets the stored item, not the echo of the request.
    return bind(request, lambda reply: _read_created(read, reply))


def _read_created(read, reply: Any) -> Result[WorkItem]:
    match tuple(record for record in _records(reply) if record.get("id")):
        case (created, *_):
            return read(str(created["id"]))
        case ():
            return err(
                "provider_error", "Azure DevOps did not return the created work item"
            )


def _transition(
    context: AdapterContext, call, read, ref: str, state: LogicalState
) -> Result[WorkItem]:
    update = [
        {
            "op": "add",
            "path": "/fields/System.State",
            "value": context.manifest.states[state],
        }
    ]
    return bind(
        payloads.number(ref, "work item"),
        lambda number: bind(
            call("write", "update", {"id": number, "updates": update}),
            lambda _: read(ref),
        ),
    )


def _comments(call, ref: str) -> Result[tuple[ArtifactRef, ...]]:
    return bind(
        payloads.number(ref, "work item"),
        lambda number: fmap(
            call("read", "list_comments", {"workItemId": number, "top": LIMIT}),
            lambda reply: artifacts.references(
                payloads.records(reply), "text", "content"
            ),
        ),
    )


def _comment(call, ref: str, draft: ArtifactDraft) -> Result[ArtifactRef]:
    return bind(
        payloads.number(ref, "work item"),
        lambda number: fmap(
            call(
                "comment",
                "add",
                {
                    "workItemId": number,
                    "text": artifacts.encode(draft),
                    "format": "Markdown",
                },
            ),
            lambda reply: artifacts.added(payloads.mapping(reply), draft),
        ),
    )
