"""Print the local tracker's work items as their parent/child tree.

Items are filed by state, so the hierarchy lives only in each record's `parentId`. This view puts
it back together: every item under its parent, children in key order, each with its state. An
item whose parent is missing is shown at the top level and marked, so nothing disappears.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err
from harness import local_tracker
from integrations.contracts import Manifest


def render(repo: Path, manifest: Manifest) -> Result[str]:
    if manifest.name != "local":
        return err(
            "tracker_tree_unsupported",
            f"the tree view reads the local tracker; {manifest.label} keeps its items remotely",
        )
    return bind(_records(repo, manifest), _draw)


def _records(repo: Path, manifest: Manifest) -> Result[tuple[dict[str, Any], ...]]:
    root = local_tracker.storage_root(repo)

    def load() -> tuple[dict[str, Any], ...]:
        return tuple(
            {**json.loads(path.read_text(encoding="utf-8")), "_folder": folder}
            for folder in dict.fromkeys(manifest.states.values())
            if (root / folder).is_dir()
            for path in sorted((root / folder).glob("*.json"))
        )

    return attempt(
        load,
        "local_storage_error",
        f"could not read the work items in {root}",
        OSError,
        ValueError,
    )


def _draw(records: tuple[dict[str, Any], ...]) -> Result[str]:
    if not records:
        return Ok("no work items yet")
    by_key = {str(record.get("key", "")): record for record in records}
    children: dict[str, list[Mapping[str, Any]]] = {}
    roots: list[Mapping[str, Any]] = []
    for record in sorted(records, key=_order):
        parent = str(record.get("parentId") or "")
        if parent and parent in by_key:
            children.setdefault(parent, []).append(record)
        else:
            roots.append(record)
    width = max(len(str(record.get("key", ""))) for record in records)
    lines: list[str] = []

    def walk(record: Mapping[str, Any], prefix: str, last: bool, top: bool) -> None:
        key = str(record.get("key", ""))
        branch = "" if top else ("└── " if last else "├── ")
        orphan = (
            f"  (parent {record['parentId']} not found)"
            if top and record.get("parentId")
            else ""
        )
        lines.append(
            f"{prefix}{branch}{key.ljust(width)}  {record.get('title', '')}"
            f"  [{record.get('_folder', '')}]{orphan}"
        )
        below = children.get(key, [])
        deeper = prefix if top else prefix + ("    " if last else "│   ")
        for index, child in enumerate(below):
            walk(child, deeper, index == len(below) - 1, False)

    for record in roots:
        walk(record, "", True, True)
    return Ok("\n".join(lines))


_KIND_ORDER = {"epic": 0, "feature": 1, "user_story": 2, "bug": 3, "task": 4}


def _order(record: Mapping[str, Any]) -> tuple[int, str]:
    return (_KIND_ORDER.get(str(record.get("kind", "")), 9), str(record.get("key", "")))
