"""Read-only tracker checks before a backlog publication batch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.result import Ok, Result, bind, err, fmap, require
from integrations import payloads
from integrations.registry import Active

ReadTool = Callable[[str, Mapping[str, Any]], Result[Any]]


@dataclass(frozen=True)
class Readiness:
    tracker: str
    ready: bool
    team: str
    needed_labels: tuple[str, ...]
    missing_labels: tuple[str, ...]
    note: str


def check(active: Active, call: ReadTool) -> Result[Readiness]:
    match active.manifest.name:
        case "linear":
            return _linear(active, call)
        case _:
            return Ok(
                Readiness(
                    active.manifest.name,
                    True,
                    "",
                    (),
                    (),
                    "Manifest values are valid; check provider authentication and permissions before writing.",
                )
            )


def _linear(active: Active, call: ReadTool) -> Result[Readiness]:
    team = active.values.get("team", "")
    needed = tuple(dict.fromkeys(active.manifest.kinds.values()))
    return bind(
        require(
            bool(team), "tracker_not_ready", "choose a Linear team before publishing"
        ),
        lambda _: fmap(
            _linear_labels(call, team),
            lambda labels: Readiness(
                "linear",
                not (
                    missing := tuple(
                        label for label in needed if label.casefold() not in labels
                    )
                ),
                team,
                needed,
                missing,
                "Create missing labels in the approved publication batch before creating any issue."
                if missing
                else "Required issue labels are present; verify write permission at publication.",
            ),
        ),
    )


def _linear_labels(
    call: ReadTool, team: str, cursor: str = "", visited: frozenset[str] = frozenset()
) -> Result[frozenset[str]]:
    return bind(
        call(
            "list_issue_labels",
            {"team": team, "limit": 250, **({"cursor": cursor} if cursor else {})},
        ),
        lambda reply: bind(
            require(
                isinstance(reply, list)
                or isinstance(reply, dict)
                and any(
                    isinstance(reply.get(key), list)
                    for key in ("labels", "nodes", "items")
                ),
                "tracker_not_ready",
                "Linear did not return a readable label list",
            ),
            lambda _: _next_labels(call, team, reply, visited),
        ),
    )


def _next_labels(
    call: ReadTool, team: str, reply: Any, visited: frozenset[str]
) -> Result[frozenset[str]]:
    records = (
        reply.get("labels", [])
        if isinstance(reply, dict) and isinstance(reply.get("labels"), list)
        else payloads.records(reply)
    )
    names = frozenset(
        str(item.get("name", "")).strip().casefold()
        for item in records
        if isinstance(item, dict) and item.get("name")
    )
    page = reply.get("pageInfo", {}) if isinstance(reply, dict) else {}
    cursor = (
        str(page.get("endCursor") or reply.get("nextCursor") or "")
        if isinstance(reply, dict)
        else ""
    )
    match (
        bool(page.get("hasNextPage")) if isinstance(page, dict) else bool(cursor),
        cursor,
    ):
        case True, str() as next_cursor if (
            next_cursor and next_cursor not in visited and len(visited) < 20
        ):
            return fmap(
                _linear_labels(call, team, next_cursor, visited | {next_cursor}),
                lambda later: names | later,
            )
        case True, _:
            return err(
                "tracker_not_ready", "Linear label pagination did not finish safely"
            )
        case _:
            return Ok(names)
