"""Plan and spec notes kept in the repository's backlog artifacts path.

The tracker is the usual home of an approved spec: publishing one needs the user's approval. A note
in the artifacts path gets the same guarantee from the approval hooks. When the user approves, the
hook pins the path and exact content of every note marked `status: approved` (`state.pin_notes`),
and only pinned content counts. A draft, a note edited after the approval, or one marked approved
without a later approval is never read as approved.

This module only reads notes. Which kinds count as a spec is the spec gate's decision.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

from harness import state  # noqa: E402
from orchestrator_core.ingest import parse_frontmatter  # noqa: E402
from orchestrator_core.project_config import load_project_config  # noqa: E402

# `ticket` is left out: the work-item templates use it for the parent of the item being drafted.
WORK_ITEM_FIELDS = ("story", "work_item")
APPROVED_STATUS = "approved"
_FRONTMATTER_BYTES = 16 * 1024
# Folders an artifacts path set to the repository root would otherwise drag into the scan.
_SKIPPED_DIRS = frozenset({"node_modules", "__pycache__"})


def artifacts_dir(project_root: Path) -> Path | None:
    """The settings' artifacts path, or None when the settings name none or cannot be read."""
    return load_project_config(project_root).resolve_artifacts_dir(project_root)


def approved_notes(project_root: Path) -> dict[str, str]:
    """Path -> content digest of each note marked `status: approved`, for an approval to pin."""
    notes: dict[str, str] = {}
    for path in _markdown_files(artifacts_dir(project_root)):
        note = _read_note(path)
        if note is not None and _approved(note[0]):
            notes[str(path.resolve())] = note[1]
    return notes


def approved_kinds_for(project_root: Path, key: str) -> set[str]:
    """The frontmatter `type` of each note naming `key` that the user approved as it reads now.

    Only pinned paths are read, so the cost follows the number of approvals, not the vault's size.
    """
    kinds: set[str] = set()
    for path, digests in state.pinned_notes(project_root).items():
        note = _read_note(Path(path))
        if note is None or note[1] not in digests:
            continue
        frontmatter = note[0]
        kind = frontmatter.get("type")
        if (
            isinstance(kind, str)
            and _approved(frontmatter)
            and any(_names_key(frontmatter.get(f), key) for f in WORK_ITEM_FIELDS)
        ):
            kinds.add(kind)
    return kinds


def _markdown_files(root: Path | None) -> Iterator[Path]:
    if root is None or not root.is_dir():
        return
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [
            d for d in subdirs if not d.startswith(".") and d not in _SKIPPED_DIRS
        ]
        for name in files:
            if name.endswith(".md"):
                yield Path(directory) / name


def _read_note(path: Path) -> tuple[dict[str, Any], str] | None:
    """The note's frontmatter and the digest of its whole content, or None when unreadable."""
    try:
        content = path.read_bytes()
    except OSError:
        return None
    head = content[:_FRONTMATTER_BYTES].decode("utf-8-sig", errors="replace")
    frontmatter, _ = parse_frontmatter(head)
    return frontmatter, hashlib.sha256(content).hexdigest()


def _approved(frontmatter: dict[str, Any]) -> bool:
    return str(frontmatter.get("status", "")).strip().lower() == APPROVED_STATUS


def _names_key(value: Any, key: str) -> bool:
    # Inline lists (`story: ["7824"]`) keep their quotes after parsing.
    values = value if isinstance(value, list) else [value]
    return any(
        str(item).strip().strip("\"'") == key for item in values if item is not None
    )
