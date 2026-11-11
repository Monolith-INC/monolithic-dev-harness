"""The bundled local tracker: the agile-backlog-toolkit's `Tickets/` folder (`harness.local_tracker`).

Each work item is a ticket file in its state's folder; its artifacts are Markdown files under
`Tickets/Attachments/<KEY>/`. Hierarchy follows the manifest's artifacts. A work item's planning
fields (its sprint, points, and hours) use the same names as a planning file's front matter
(`integrations.planning`). A sprint is a `capacity-<sprint>.json` file beside `Tickets/`; the
current sprint is the one whose dates cover today.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, oks, require, sequence
from harness import local_tracker
from integrations import artifacts
from integrations.contracts import (
    AdapterContext,
    ArtifactDraft,
    ArtifactRef,
    FieldNames,
    LogicalState,
    Manifest,
    Page,
    TrackerOps,
    WorkItem,
    WorkItemKind,
    changed_fields,
)
from integrations.planning import IterationReading, Sprint, is_current
from integrations.planning_files import (
    ASSIGNED_TO,
    ITERATION,
    POINTS,
    RECORDED_HOURS,
    planning_item,
    read_capacity_file,
)

PAGE_SIZE = 50
FIELDS = FieldNames(
    "title", "description", POINTS, ASSIGNED_TO, ITERATION, "tags", "priority"
)
PREFIXES = {
    WorkItemKind.EPIC: "EPIC",
    WorkItemKind.FEATURE: "FEATURE",
    WorkItemKind.USER_STORY: "STORY",
    WorkItemKind.TASK: "TASK",
    WorkItemKind.BUG: "BUG",
}

Record = tuple[Path, Mapping[str, Any]]


def adapter(context: AdapterContext) -> TrackerOps:
    root = local_tracker.storage_root(context.repo)
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
        update_work_item=lambda ref, changes: bind(
            changed_fields(changes, FIELDS, RECORDED_HOURS),
            lambda fields: bind(
                _find(context, root, ref),
                lambda found: bind(
                    _parent_fields(context, root, found, changes.parent),
                    lambda parent: _update(context, found, {**fields, **parent}),
                ),
            ),
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
        current_sprint=lambda: _current_sprint(context.repo),
        sprint_capacity=lambda ref: bind(
            _named_sprint(context.repo, ref), lambda name: _capacity(context.repo, name)
        ),
        sprint_items=lambda ref: bind(
            _named_sprint(context.repo, ref),
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
        records_hours=True,
    )


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _records(context: AdapterContext, root: Path) -> Result[tuple[Record, ...]]:
    return attempt(
        lambda: local_tracker.records(root, context.manifest),
        "local_storage_error",
        f"could not read the tickets in {root}",
        OSError,
        ValueError,
        UnicodeDecodeError,
    )


def _reread(context: AdapterContext, path: Path, state: str) -> Result[Record]:
    """Read one ticket file back from disk after writing it."""
    return bind(
        attempt(
            lambda: local_tracker.read(path, state),
            "local_storage_error",
            f"could not read {path.name}",
            OSError,
            ValueError,
            UnicodeDecodeError,
        ),
        lambda record: (
            Ok((path, record))
            if record is not None
            else err("local_storage_error", f"{path.name} lost its provider_id")
        ),
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
        tags=tuple(str(tag) for tag in record.get("tags") or ()),
        priority=int(record["priority"])
        if record.get("priority") is not None
        else None,
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


def _parent_fields(
    context: AdapterContext, root: Path, found: Record, parent: str | None
) -> Result[dict[str, Any]]:
    """The record change that moves the item under `parent`, which must be allowed to hold it,
    as at create; nothing when no move was asked for."""
    if parent is None:
        return Ok({})
    kind = WorkItemKind(str(found[1]["kind"]))
    return bind(
        _find(context, root, parent),
        lambda target: (
            Ok({"parentId": target[1]["key"]})
            if _allowed_child(context, WorkItemKind(str(target[1]["kind"])), kind)
            else err(
                "invalid_parent",
                f"a {target[1]['kind']} cannot contain a {kind.value}",
            )
        ),
    )


def _next_key(root: Path, manifest: Manifest, kind: WorkItemKind) -> str:
    """The next number across every kind and every draft's reserved one, so the number alone
    names the file."""
    numbers = local_tracker.used_numbers(root, manifest)
    return f"{PREFIXES[kind]}-{max(numbers, default=0) + 1:04d}"


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
                # Reading every item first surfaces a broken ticket file before anything is written.
                lambda _found: _store_new(
                    context, root, kind, title, description, found_parent
                ),
            ),
        ),
    )


def _store_new(
    context: AdapterContext,
    root: Path,
    kind: WorkItemKind,
    title: str,
    description: str,
    parent: Record | None,
) -> Result[WorkItem]:
    """Write the item's ticket file. A draft with the same body becomes this item: its front matter
    (points, language, tags) is kept, the number its file name reserved becomes the item's, and the
    draft file is replaced."""
    draft = next(
        (
            (file, fields)
            for file, fields, body in local_tracker.drafts(root)
            if body.strip() == description.strip()
        ),
        None,
    )
    reserved = (
        local_tracker.draft_number(draft[0], root, context.manifest) if draft else None
    )
    key = (
        f"{PREFIXES[kind]}-{reserved:04d}"
        if reserved is not None
        else _next_key(root, context.manifest, kind)
    )
    record = {
        **(local_tracker.draft_fields(draft[1]) if draft else {}),
        "key": key,
        "title": title,
        "kind": kind.value,
        "description": description,
        "parentId": parent[1]["key"] if parent else "",
        "date": _today(),
    }
    state = LogicalState.BACKLOG
    path = root / context.manifest.states[state] / local_tracker.file_name(key, title)

    def store() -> None:
        local_tracker.write(path, record)
        if draft and draft[0] != path:
            draft[0].unlink()

    return bind(
        attempt(store, "local_storage_error", f"could not write {path.name}", OSError),
        lambda _: fmap(
            _reread(context, path, state.value), lambda read: _item(read[1])
        ),
    )


def _write(path: Path, record: Mapping[str, Any]) -> Result[None]:
    return attempt(
        lambda: local_tracker.write(path, record),
        "local_storage_error",
        f"could not write {path.name}",
        OSError,
    )


def _update(
    context: AdapterContext, found: Record, fields: Mapping[str, Any]
) -> Result[WorkItem]:
    """Write the named fields, then read the item back from disk."""
    path, record = found
    return bind(
        _write(path, {**record, **fields}),
        lambda _: fmap(
            _reread(context, path, str(record["state"])), lambda read: _item(read[1])
        ),
    )


def _move(
    context: AdapterContext, root: Path, found: Record, state: LogicalState
) -> Result[WorkItem]:
    path, record = found
    target = root / context.manifest.states[state] / path.name
    return bind(
        _write(target, record),
        lambda _: bind(
            attempt(
                lambda: path.unlink() if target != path else None,
                "local_storage_error",
                f"could not move {path.name}",
                OSError,
            ),
            lambda _: fmap(
                _reread(context, target, state.value),
                lambda read: _item({**read[1], "state": state.value}),
            ),
        ),
    )


def _artifact_folder(root: Path, record: Mapping[str, Any]) -> Path:
    return local_tracker.attachments(root, str(record["key"]))


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
            _write(path, {**record, "links": [*links, link]}),
            lambda _: reply,
        )
    )


def _capacity(repo: Path, name: str) -> Result[IterationReading]:
    path = local_tracker.capacity_file(repo, _safe(name))
    return bind(
        require(
            path.is_file(),
            "no_capacity",
            f"sprint {name!r} has no capacity file at {path.name} beside Tickets/",
        ),
        lambda _: read_capacity_file(path, name),
    )


def _current_sprint(repo: Path) -> Result[Sprint]:
    """The sprint file whose dates cover today; of several, the one that started last."""
    files = sorted(local_tracker.storage_root(repo).parent.glob("capacity-*.json"))
    today = datetime.now(UTC).date()
    return bind(
        sequence(
            tuple(
                fmap(
                    read_capacity_file(path, path.stem.removeprefix("capacity-")),
                    lambda reading: reading.capacity,
                )
                for path in files
            )
        ),
        lambda sprints: next(
            (
                Ok(
                    Sprint(
                        s.iteration_ref,
                        s.iteration_ref,
                        s.iteration_ref,
                        s.start_date,
                        s.finish_date,
                    )
                )
                for s in sorted(
                    (
                        s
                        for s in sprints
                        if s.start_date
                        and s.finish_date
                        and s.start_date <= today <= s.finish_date
                    ),
                    key=lambda s: s.start_date,
                    reverse=True,
                )
            ),
            err(
                "no_current_sprint",
                "no sprint file beside Tickets/ covers today; read: "
                + (", ".join(path.name for path in files) or "none"),
            ),
        ),
    )


def _named_sprint(repo: Path, ref: str) -> Result[str]:
    """The sprint's name: the one named, or the current one's."""
    return (
        fmap(_current_sprint(repo), lambda sprint: sprint.name)
        if is_current(ref)
        else Ok(ref.strip())
    )
