"""The bundled local tracker's files: the agile-backlog-toolkit's `Tickets/` folder.

Each work item is one Markdown file in the toolkit's ticket format (`references/ticket-structure.md`):
front matter (`type: ticket`, `work_item_type`, `provider: local`, `provider_id`, `parent_id`,
planning fields), then the item's description, word for word, as the body. The folder holds its
state, as the toolkit's filesystem provider reads it:

    Tickets/Ready/<NNNN>-<slug>.md        new and refined items
    Tickets/InProgress/<NNNN>-<slug>.md   items being worked on
    Tickets/Done/<NNNN>-<slug>.md         finished (or canceled) items
    Tickets/Attachments/<KEY>/<file>.md   an item's artifacts, in the shared artifact format
    capacity-<sprint>.json                a sprint's dates and team, beside `Tickets/`

A file with no `provider_id` is a draft, not an item: the toolkit's skills write drafts here, and
creating the item replaces its draft. Keys are `<PREFIX>-<number>` (`STORY-0007`); the number is
unique across kinds, so it alone names the file. Every worktree of a clone reads the main
worktree's `Tickets/`, so a linked worktree sees the same items.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.result import Result, attempt
from integrations.contracts import Manifest

_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

from orchestrator_core.ingest import parse_frontmatter  # noqa: E402

ROOT = Path("Tickets")
ATTACHMENTS = "Attachments"
WORK_ITEM_TYPES = {
    "epic": "Epic",
    "feature": "Feature",
    "user_story": "User Story",
    "task": "Task",
    "bug": "Bug",
}
_KINDS = {label: kind for kind, label in WORK_ITEM_TYPES.items()}
# Front matter the record keeps under its own names; everything else is a planning field.
_OWN = frozenset(
    {
        "type",
        "title",
        "work_item_type",
        "provider",
        "provider_id",
        "parent_id",
        "date",
        "links",
    }
)
# Record fields the file holds elsewhere: in its name, its folder, its body or `parent_id`.
_RECORD_ONLY = frozenset({"key", "id", "kind", "state", "description", "parentId"})

Record = dict[str, Any]


# A checkout made for another project's work (adoption's recovery worktree) names that project here.
SHARED_WITH = Path(".harness/state/tracker-project")


def storage_root(repo: Path) -> Path:
    """The project's own `Tickets/`, whether or not the project is versioned, or the `Tickets/` of
    the project this checkout was made for."""
    pointer = repo / SHARED_WITH
    return (
        Path(pointer.read_text(encoding="utf-8").strip()) / ROOT
        if pointer.is_file()
        else repo / ROOT
    )


def capacity_file(repo: Path, sprint: str) -> Path:
    return storage_root(repo).parent / f"capacity-{sprint}.json"


def folders(manifest: Manifest) -> tuple[str, ...]:
    return tuple(dict.fromkeys(manifest.states.values()))


def describe(repo: Path, manifest: Manifest) -> dict[str, object]:
    root = storage_root(repo)
    return {
        "path": str(root),
        "ready": all((root / name).is_dir() for name in folders(manifest)),
        "folders": list(folders(manifest)),
        "work_item_count": sum(
            1
            for name in folders(manifest)
            for path in _files(root / name)
            if is_item(path)
        ),
    }


def prepare(repo: Path, manifest: Manifest) -> Result[dict[str, object]]:
    def create() -> dict[str, object]:
        root = storage_root(repo)
        for name in folders(manifest):
            (root / name).mkdir(parents=True, exist_ok=True)
        return describe(repo, manifest)

    return attempt(
        create,
        "local_tracker_unwritable",
        f"could not prepare local tracker at {storage_root(repo)}",
        OSError,
    )


def _files(folder: Path) -> tuple[Path, ...]:
    return tuple(sorted(folder.glob("*.md"))) if folder.is_dir() else ()


def is_item(path: Path) -> bool:
    """Whether a ticket file is a tracked item (it has a `provider_id`), not a draft."""
    try:
        frontmatter, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return False
    return bool(frontmatter.get("provider_id"))


def read(path: Path, state: str) -> Record | None:
    """The record a ticket file holds, or None for a draft. Raises OSError or ValueError."""
    frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    key = str(frontmatter.get("provider_id") or "")
    if not key:
        return None
    kind = _KINDS.get(str(frontmatter.get("work_item_type", "")))
    if kind is None:
        raise ValueError(f"{path.name} has an unknown work_item_type")
    return {
        **{name: value for name, value in frontmatter.items() if name not in _OWN},
        "key": key,
        "id": key,
        "title": str(frontmatter.get("title", "")),
        "kind": kind,
        "state": state,
        "description": body.removeprefix("\n").removesuffix("\n"),
        "parentId": str(frontmatter.get("parent_id") or ""),
        "links": [_link(entry) for entry in frontmatter.get("links") or ()],
        "date": str(frontmatter.get("date", "")),
    }


def records(root: Path, manifest: Manifest) -> tuple[tuple[Path, Record], ...]:
    """Every tracked item, each with its file. Raises OSError or ValueError."""
    states = {
        folder: state.value for state, folder in reversed(manifest.states.items())
    }
    return tuple(
        (path, record)
        for folder in folders(manifest)
        for path in _files(root / folder)
        if (record := read(path, states[folder])) is not None
    )


def drafts(root: Path) -> tuple[tuple[Path, dict[str, Any], str], ...]:
    """Every draft (a ticket file with no `provider_id`): its file, front matter and body."""
    found = []
    for path in sorted(root.rglob("*.md")) if root.is_dir() else ():
        if ATTACHMENTS in path.relative_to(root).parts:
            continue
        try:
            frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if not frontmatter.get("provider_id"):
            found.append(
                (path, frontmatter, body.removeprefix("\n").removesuffix("\n"))
            )
    return tuple(found)


_NUMBERED = re.compile(r"^(\d+)-(.+?)(?:\.md)?$")
_KEY_NUMBER = re.compile(r"^[A-Z]+-(\d+)$")


def numbered(name: str) -> tuple[int, str] | None:
    """The number and slug of a `<number>-<slug>` name, or None."""
    match = _NUMBERED.match(name)
    return (int(match.group(1)), match.group(2)) if match else None


def used_numbers(root: Path, manifest: Manifest) -> set[int]:
    """Numbers held by tracked items and by drafts (whose file names reserve theirs)."""
    held = {
        int(match.group(1))
        for _, record in records(root, manifest)
        if (match := _KEY_NUMBER.match(str(record.get("key", ""))))
    }
    return held | {
        found[0] for path, _, _ in drafts(root) if (found := numbered(path.name))
    }


def draft_number(path: Path, root: Path, manifest: Manifest) -> int | None:
    """The number a draft's file name reserved, unless a tracked item already holds it."""
    found = numbered(path.name)
    taken = {
        int(match.group(1))
        for _, record in records(root, manifest)
        if (match := _KEY_NUMBER.match(str(record.get("key", ""))))
    }
    return found[0] if found and found[0] not in taken else None


def draft_fields(frontmatter: Mapping[str, Any]) -> dict[str, Any]:
    """What an item keeps from its draft's front matter: points, hours, language, tags and the
    like. Its identity, type and parent come from the tracker, and `status` is never kept."""
    return {
        name: value
        for name, value in frontmatter.items()
        if name not in _OWN and name not in _RECORD_ONLY and name != "status"
    }


def body_digest(text: str) -> str:
    """The digest of a ticket's body (front matter left out), as an item's description is compared."""
    _, body = parse_frontmatter(text)
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()


def _link(entry: str) -> dict[str, str]:
    kind, _, url = str(entry).partition(" ")
    return {"type": kind, "url": url}


def _scalar(value: Any) -> str:
    match value:
        case bool():
            return "true" if value else "false"
        case int() | float():
            return str(value)
        case list() | tuple():
            return "[" + ", ".join(str(item) for item in value) + "]"
        case _:
            return '"' + str(value).replace("\n", " ").replace('"', "'") + '"'


def render(record: Mapping[str, Any]) -> str:
    """A record as its ticket file."""
    lines = [
        "---",
        f"title: {_scalar(record['title'])}",
        "type: ticket",
        f"work_item_type: {WORK_ITEM_TYPES[str(record['kind'])]}",
        "provider: local",
        f"provider_id: {_scalar(record['key'])}",
    ]
    if record.get("parentId"):
        lines.append(f"parent_id: {_scalar(record['parentId'])}")
    if record.get("date"):
        lines.append(f"date: {record['date']}")
    for name, value in record.items():
        if name in _OWN or name in _RECORD_ONLY or value in (None, ""):
            continue
        lines.append(f"{name}: {_scalar(value)}")
    if record.get("links"):
        entries = ", ".join(f"{link['type']} {link['url']}" for link in record["links"])
        lines.append(f"links: [{entries}]")
    lines.extend(("---", "", str(record.get("description", ""))))
    return "\n".join(lines) + "\n"


def file_name(key: str, title: str) -> str:
    """`<number>-<slug>.md`, the toolkit's ticket file name."""
    return f"{key_number(key)}-{title_slug(title)}.md"


def key_number(key: str) -> str:
    """The number the toolkit's file names use: the key's last part (`STORY-0001` → `0001`)."""
    return key.rpartition("-")[2].lower()


def title_slug(title: str) -> str:
    """The title in lowercase ASCII words joined by hyphens, at most 60 characters."""
    ascii_title = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:60].strip("-")
    return slug or "item"


def write(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(record), encoding="utf-8")


def attachments(root: Path, key: str) -> Path:
    return root / ATTACHMENTS / key
