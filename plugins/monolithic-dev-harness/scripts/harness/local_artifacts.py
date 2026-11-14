"""Plan and spec notes kept in the repository's backlog artifacts path.

The tracker is the usual home of an approved spec: publishing one needs the user's approval. A note
in the artifacts path gets the same guarantee from the approval hooks. When the user approves, the
hook pins the path and content of every note the approval reviewed (`state.pin_notes`), and only
pinned content counts. The note's own `status` (`draft`, then `active` once accepted) is not part
of what is pinned; a note never reviewed, or edited after the approval, is never read as approved.

This module only reads notes. Which kinds count as a spec is the spec gate's decision.
"""

from __future__ import annotations

import sys
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

from core.result import value_or  # noqa: E402
from harness import state  # noqa: E402
from harness.workflow import document_digest, file_digest  # noqa: E402
from orchestrator_core.ingest import parse_frontmatter  # noqa: E402
from orchestrator_core.project_config import load_project_config  # noqa: E402

# `ticket` is left out: the work-item templates use it for the parent of the item being drafted.
WORK_ITEM_FIELDS = ("story", "work_item")
_FRONTMATTER_BYTES = 16 * 1024


def artifacts_dir(project_root: Path) -> Path | None:
    """The settings' artifacts path, or None when the settings name none or cannot be read."""
    return load_project_config(project_root).resolve_artifacts_dir(project_root)


@dataclass(frozen=True)
class Note:
    """A note's frontmatter and the digest of its content (`workflow.document_digest`)."""

    frontmatter: dict[str, Any]
    digest: str

    @property
    def kind(self) -> str:
        return str(self.frontmatter.get("type") or "")

    @property
    def work_items(self) -> tuple[str, ...]:
        """The work items the note names in its `story` or `work_item` field, one or a list."""
        named: list[str] = []
        for name in WORK_ITEM_FIELDS:
            value = self.frontmatter.get(name)
            for item in value if isinstance(value, list) else [value]:
                # Inline lists (`story: ["7824"]`) keep their quotes after parsing.
                text = str(item).strip().strip("\"'") if item is not None else ""
                if text:
                    named.append(text)
        return tuple(dict.fromkeys(named))


def note(path: Path) -> Note | None:
    """The note at `path`, or None when it cannot be read."""
    try:
        content = path.read_bytes()
    except OSError:
        return None
    head = content[:_FRONTMATTER_BYTES].decode("utf-8-sig", errors="replace")
    frontmatter, _ = parse_frontmatter(head)
    return Note(frontmatter, document_digest(content))


def reviewed_notes(project_root: Path, reviewed: Iterable[str]) -> dict[str, str]:
    """Path -> content digest of each reviewed file that is a note in the artifacts path."""
    folder = artifacts_dir(project_root)
    notes: dict[str, str] = {}
    if folder is None:
        return notes
    root = folder.resolve()
    for name in reviewed:
        path = Path(name).resolve()
        found = note(path) if path.is_relative_to(root) else None
        if found is not None and found.kind:
            notes[str(path)] = found.digest
    return notes


def approved_kinds_for(project_root: Path, key: str) -> set[str]:
    """The frontmatter `type` of each note naming `key` that the user approved as it reads now.

    Only pinned paths are read, so the cost follows the number of approvals, not the vault's size.
    """
    kinds: set[str] = set()
    for path, digests in current_pins(project_root).items():
        found = note(Path(path))
        if (
            found is not None
            and found.digest in digests
            and found.kind
            and key in found.work_items
        ):
            kinds.add(found.kind)
    return kinds


def relocated(project_root: Path, path: Path, digests: Collection[str]) -> Path | None:
    """Where a file recorded at `path`, now gone, is after the artifacts path moved.

    That is the deepest trailing part of `path` under the current artifacts path whose content has
    one of `digests`, so only the content that was recorded matches; None when there is none or
    `path` still exists.
    """
    folder = artifacts_dir(project_root)
    if folder is None or path.exists():
        return None
    root = project_root.resolve()
    parts = (
        path.relative_to(root).parts if path.is_relative_to(root) else path.parts[1:]
    )
    return next(
        (
            candidate
            for start in range(len(parts))
            for candidate in (folder.resolve().joinpath(*parts[start:]),)
            if candidate.is_file() and value_or(file_digest(candidate), None) in digests
        ),
        None,
    )


def current_pins(project_root: Path) -> dict[str, set[str]]:
    """`state.pinned_notes`, each pin whose note is gone keyed where `relocated` finds it."""
    pins: dict[str, set[str]] = {}
    for path, digests in state.pinned_notes(project_root).items():
        found = relocated(project_root, Path(path), digests)
        pins.setdefault(str(found) if found else path, set()).update(digests)
    return pins
