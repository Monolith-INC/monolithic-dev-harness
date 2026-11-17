"""Conservative, bounded validation of source fingerprints in a knowledge store."""

import hashlib
import re
from pathlib import Path

from project_knowledge.store import KnowledgeStore, StoreError

from core.result import Ok, attempt

_SOURCE = re.compile(r"^(.+)#sha256:([0-9a-f]{64})$")
_MAX_FILES = 16
_MAX_BYTES = 2 * 1024 * 1024


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        content = stream.read(_MAX_BYTES + 1)
    return hashlib.sha256(content).hexdigest() if len(content) <= _MAX_BYTES else ""


def _source(repo: Path, item: object) -> tuple[Path, str] | None:
    match item:
        case str() as text if (matched := _SOURCE.fullmatch(text)) is not None:
            relative, digest = matched.groups()
            path = Path(relative)
            match path.is_absolute() or ".." in path.parts:
                case True:
                    return None
                case False:
                    resolved = (repo / path).resolve()
                    return (resolved, digest) if resolved.is_relative_to(repo) else None
        case _:
            return None


def _checked(repo: Path, root: Path) -> bool:
    units = tuple(
        unit
        for unit in KnowledgeStore(root).units.values()
        if unit.fields.get("status", "current") == "current"
    )
    declared = tuple(unit.fields.get("sources", ()) for unit in units)
    match bool(units) and all(
        isinstance(items, (list, tuple)) and bool(items) for items in declared
    ):
        case False:
            return False
        case True:
            pass
    sources = tuple(_source(repo, item) for items in declared for item in items)
    match (
        bool(sources)
        and len(sources) <= _MAX_FILES
        and all(item is not None for item in sources)
    ):
        case False:
            return False
        case True:
            pass
    pairs = tuple(item for item in sources if item is not None)
    match sum(path.stat().st_size for path, _ in pairs) <= _MAX_BYTES:
        case False:
            return False
        case True:
            return all(_digest(path) == digest for path, digest in pairs)


def verified_fresh(repo: Path, root: Path) -> bool:
    """Unknown, missing, oversized or invalid sources are not evidence of freshness."""
    result = attempt(
        lambda: _checked(repo.resolve(), root.resolve()),
        "knowledge_freshness_unknown",
        "Could not verify knowledge freshness",
        OSError,
        ValueError,
        UnicodeError,
        StoreError,
    )
    return isinstance(result, Ok) and result.value
