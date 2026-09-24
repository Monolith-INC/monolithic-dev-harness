"""Spec-like artifacts kept in the repository's backlog artifacts path (`backlog.artifacts_path`)."""

from __future__ import annotations

import sys
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

from harness.config import load_policy  # noqa: E402
from orchestrator_core.ingest import parse_frontmatter  # noqa: E402

WORK_ITEM_FIELDS = ("story", "ticket", "work_item")
_FRONTMATTER_BYTES = 16 * 1024


def artifacts_root(project_root: Path) -> Path | None:
    configured = str(
        load_policy(project_root).get("backlog", {}).get("artifacts_path") or ""
    ).strip()
    return (project_root / configured).resolve() if configured else None


def has_local_spec_artifact(
    project_root: Path,
    key: str,
    accepted_kinds: Collection[str],
    normalize_kind: Callable[[str], str],
) -> bool:
    root = artifacts_root(project_root)
    if root is None or not root.is_dir():
        return False
    return any(
        _is_spec_for(path, key, accepted_kinds, normalize_kind)
        for path in root.rglob("*.md")
    )


def _is_spec_for(
    path: Path,
    key: str,
    accepted_kinds: Collection[str],
    normalize_kind: Callable[[str], str],
) -> bool:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            head = handle.read(_FRONTMATTER_BYTES)
    except OSError:
        return False
    frontmatter, _ = parse_frontmatter(head)
    kind = frontmatter.get("type")
    return (
        isinstance(kind, str)
        and normalize_kind(kind) in accepted_kinds
        and any(_names_key(frontmatter.get(field), key) for field in WORK_ITEM_FIELDS)
    )


def _names_key(value: Any, key: str) -> bool:
    values = value if isinstance(value, list) else [value]
    return any(
        str(item).strip().strip("\"'") == key for item in values if item is not None
    )
