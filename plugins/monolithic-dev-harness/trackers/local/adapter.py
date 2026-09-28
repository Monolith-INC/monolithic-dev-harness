"""A tracker kept in the repository: one JSON file per work item, one Markdown file per artifact.

    .harness/tracker/<state>/<KEY>.json          a work item, in the folder of its state
    .harness/tracker/artifacts/<KEY>/<file>.md   its artifacts, in the shared artifact format
    .harness/tracker/capacity/<sprint>.json      a sprint's dates and team, in the capacity format

Keys are `<PREFIX>-<number>` (`STORY-0007`). Hierarchy follows the manifest's artifacts. A work
item's planning fields (its sprint, points, and hours) use the same names as a planning file's
front matter (`integrations.planning`). Planning reads these files, so it needs no replies, but it
does need the sprint named: there is no "current" sprint to fall back on.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, oks, require, sequence
from harness.state import write_json
from integrations import artifacts
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
from integrations.planning import (
    ITERATION,
    planning_item,
    read_capacity_file,
    recorded_hours,
)

ROOT = Path(".harness") / "tracker"
PAGE_SIZE = 50
PREFIXES = {
    WorkItemKind.EPIC: "EPIC",
    WorkItemKind.FEATURE: "FEATURE",
    WorkItemKind.USER_STORY: "STORY",
    WorkItemKind.TASK: "TASK",
    WorkItemKind.BUG: "BUG",
}

Record = tuple[Path, Mapping[str, Any]]


def adapter(context: AdapterContext) -> TrackerOps:
    root = context.repo / ROOT
    return TrackerOps(
        get_work_item=lambda ref: fmap(
            _find(context, root, ref), lambda found: _item(found[1])
        ),
        search_work_items=lambda query, cursor: fmap(
            _records(context, root), lambda found: _page(found, query, cursor)
        ),
        create_work_item=lambda kind, title, description, parent: _create(
            context, root, kind, title, description, parent
        ),
        transition_work_item=lambda ref, state: bind(
            _find(context, root, ref), lambda found: _move(context, root, found, state)
        ),
        list_children=lambda ref: bind(
            _find(context, root, ref),
            lambda parent: fmap(
                _records(context, root),
                lambda found: tuple(
                    _item(record)
                    for _, record in found
                    if record.get("parentId") == parent[1]["id"]
                ),
            ),
        ),
        list_artifacts=lambda ref: bind(
            _find(context, root, ref), lambda found: _artifacts(root, found[1])
        ),
        add_artifact=lambda ref, draft: bind(
            _find(context, root, ref),
            lambda found: _add_artifact(root, found[1], draft),
        ),
        link_development_artifact=lambda ref, url, kind: bind(
            _find(context, root, ref), lambda found: _link(found, url, kind)
        ),
        read_iteration=lambda replies, ref: bind(
            _sprint(ref),
            lambda name: read_capacity_file(
                root / "capacity" / f"{_safe(name)}.json", name
            ),
        ),
        iteration_items=lambda replies, ref: bind(
            _sprint(ref),
            lambda name: fmap(
                _records(context, root),
                lambda found: tuple(
                    planning_item(
                        str(record["key"]),
                        str(record.get("title", "")),
                        str(record.get("kind", "")),
                        record,
                    )
                    for _, record in found
                    if record.get("key") and str(record.get(ITERATION) or "") == name
                ),
            ),
        ),
        hour_fields=recorded_hours,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_folders(context: AdapterContext, root: Path) -> tuple[Path, ...]:
    return tuple(root / name for name in context.manifest.states.values())


def _read(path: Path) -> Result[Record]:
    return bind(
        attempt(
            lambda: json.loads(path.read_text(encoding="utf-8")),
            "local_storage_error",
            f"could not read {path.name}",
            OSError,
            ValueError,
        ),
        lambda record: (
            Ok((path, record))
            if isinstance(record, dict)
            else err("local_storage_error", f"{path.name} is not an object")
        ),
    )


def _records(context: AdapterContext, root: Path) -> Result[tuple[Record, ...]]:
    return sequence(
        _read(path)
        for folder in _state_folders(context, root)
        if folder.is_dir()
        for path in sorted(folder.glob("*.json"))
    )


def _find(context: AdapterContext, root: Path, ref: str) -> Result[Record]:
    wanted = str(ref).strip().upper()
    return bind(
        _records(context, root),
        lambda found: next(
            (
                Ok(record)
                for record in found
                if str(record[1].get("key", "")).upper() == wanted
            ),
            err("work_item_not_found", f"local work item not found: {ref}"),
        ),
    )


def _item(record: Mapping[str, Any]) -> WorkItem:
    return WorkItem(
        id=str(record["key"]),
        key=str(record["key"]),
        title=str(record.get("title", "")),
        kind=WorkItemKind(str(record["kind"])),
        state=LogicalState(str(record["state"])),
        url=str(record["key"]),
        description=str(record.get("description", "")),
        parent_id=str(record.get("parentId") or ""),
        provider_data=record,
    )


def _page(found: tuple[Record, ...], query: str, cursor: str) -> Page:
    needle = query.strip().lower()
    matches = tuple(
        sorted(
            (
                _item(record)
                for _, record in found
                if not needle
                or any(
                    needle in str(record.get(key, "")).lower()
                    for key in ("key", "title", "description")
                )
            ),
            key=lambda item: item.key,
        )
    )
    start = int(cursor) if cursor.isdigit() else 0
    end = start + PAGE_SIZE
    return Page(matches[start:end], str(end) if end < len(matches) else "")


def _allowed_child(
    context: AdapterContext, parent_kind: WorkItemKind, kind: WorkItemKind
) -> bool:
    kinds = context.manifest.kinds
    children = next(
        (
            artifact.children
            for artifact in context.manifest.artifacts
            if artifact.name == kinds[parent_kind]
        ),
        (),
    )
    return kinds[kind] in children


def _next_key(found: tuple[Record, ...], kind: WorkItemKind) -> str:
    prefix = PREFIXES[kind]
    pattern = re.compile(rf"^{prefix}-(\d+)$")
    numbers = tuple(
        int(match.group(1))
        for _, record in found
        if (match := pattern.match(str(record.get("key", ""))))
    )
    return f"{prefix}-{max(numbers, default=0) + 1:04d}"


def _create(
    context: AdapterContext,
    root: Path,
    kind: WorkItemKind,
    title: str,
    description: str,
    parent: str,
) -> Result[WorkItem]:
    parent_record = _find(context, root, parent) if parent else Ok(None)
    return bind(
        parent_record,
        lambda found_parent: bind(
            require(
                found_parent is None
                or _allowed_child(context, WorkItemKind(found_parent[1]["kind"]), kind),
                "invalid_hierarchy",
                f"a {found_parent[1]['kind'] if found_parent else ''} cannot contain a {kind.value}",
            ),
            lambda _: bind(
                _records(context, root),
                lambda found: _store_new(
                    context, root, found, kind, title, description, found_parent
                ),
            ),
        ),
    )


def _store_new(
    context: AdapterContext,
    root: Path,
    found: tuple[Record, ...],
    kind: WorkItemKind,
    title: str,
    description: str,
    parent: Record | None,
) -> Result[WorkItem]:
    key = _next_key(found, kind)
    now = _now()
    record = {
        "key": key,
        "id": key,
        "title": title,
        "kind": kind.value,
        "state": LogicalState.BACKLOG.value,
        "description": description,
        "parentId": parent[1]["key"] if parent else "",
        "links": [],
        "createdAt": now,
        "updatedAt": now,
    }
    folder = root / context.manifest.states[LogicalState.BACKLOG]
    return fmap(_write(folder / f"{key}.json", record), lambda _: _item(record))


def _write(path: Path, record: Mapping[str, Any]) -> Result[None]:
    return attempt(
        lambda: write_json(path, dict(record)),
        "local_storage_error",
        f"could not write {path.name}",
        OSError,
    )


def _move(
    context: AdapterContext, root: Path, found: Record, state: LogicalState
) -> Result[WorkItem]:
    path, record = found
    updated = {**record, "state": state.value, "updatedAt": _now()}
    target = root / context.manifest.states[state] / path.name
    return bind(
        _write(target, updated),
        lambda _: fmap(
            attempt(
                lambda: path.unlink() if target != path else None,
                "local_storage_error",
                f"could not move {path.name}",
                OSError,
            ),
            lambda _: _item(updated),
        ),
    )


def _artifact_folder(root: Path, record: Mapping[str, Any]) -> Path:
    return root / "artifacts" / str(record["key"])


def _artifacts(
    root: Path, record: Mapping[str, Any]
) -> Result[tuple[ArtifactRef, ...]]:
    folder = _artifact_folder(root, record)
    files = tuple(sorted(folder.glob("*.md"))) if folder.is_dir() else ()
    return fmap(
        sequence(
            attempt(
                lambda path=path: (path, path.read_text(encoding="utf-8")),
                "local_storage_error",
                f"could not read {path.name}",
                OSError,
            )
            for path in files
        ),
        lambda texts: oks(
            artifacts.reference(_relative(root, path), _relative(root, path), stored)
            for path, stored in texts
        ),
    )


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "artifact"


def _add_artifact(
    root: Path, record: Mapping[str, Any], draft: ArtifactDraft
) -> Result[ArtifactRef]:
    path = (
        _artifact_folder(root, record)
        / f"{_safe(draft.kind)}--{_safe(draft.title)}--r{_safe(draft.revision)}.md"
    )

    def store() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifacts.encode(draft), encoding="utf-8")

    return fmap(
        attempt(store, "local_storage_error", f"could not write {path.name}", OSError),
        lambda _: ArtifactRef(
            _relative(root, path),
            draft.kind,
            draft.title,
            draft.revision,
            _relative(root, path),
            draft.content,
        ),
    )


def _link(found: Record, url: str, kind: str) -> Result[Mapping[str, Any]]:
    path, record = found
    link = {"url": url, "type": kind}
    links = tuple(record.get("links") or ())
    reply = {
        "linked": True,
        "mechanism": "local-record",
        "workItem": record["key"],
        **link,
    }
    return (
        Ok(reply)
        if link in links
        else fmap(
            _write(path, {**record, "links": [*links, link], "updatedAt": _now()}),
            lambda _: reply,
        )
    )


def _sprint(ref: str) -> Result[str]:
    name = ref.strip()
    return (
        Ok(name)
        if name
        else err(
            "invalid_request",
            "name the sprint: the local tracker reads .harness/tracker/capacity/<sprint>.json",
        )
    )
