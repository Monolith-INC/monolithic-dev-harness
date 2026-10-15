"""The project's code as content, never as version control.

Which files are code (the settings' source and test globs, outside the planning folder), a digest
per file, one digest for all of them, and what changed since a work session was linked. Check,
review, and manual-check evidence is keyed to that one digest, so it describes exactly the code on
disk and any later change invalidates it, whether or not the project uses Git.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

from core.result import Err, Ok
from harness import globs, local_artifacts, settings, state
from policy.commands import is_code

BASELINE = "code-baseline.json"
# Folders never walked: hidden ones (.git, .harness, tool caches) and dependency stores.
_SKIPPED = frozenset({"node_modules", "__pycache__"})


def patterns(repo: Path) -> list[str] | None:
    """The settings' source and test globs, or None (every file is code) when they name none."""
    match settings.load(repo):
        case Ok(chosen):
            found = [
                pattern
                for group in chosen.tests_required
                for pattern in (*group.source, *group.tests)
            ]
            return found or None
        case Err():
            return None


def planning_folder(repo: Path) -> str:
    """The artifacts path relative to the project, when it lies inside it."""
    root = repo.resolve()
    match local_artifacts.artifacts_dir(repo):
        case Path() as folder if (
            folder.resolve() != root and folder.resolve().is_relative_to(root)
        ):
            return folder.resolve().relative_to(root).as_posix()
        case _:
            return ""


def evidenced(repo: Path) -> list[str]:
    """Files evidence speaks for besides code: guarded paths and the globs that trigger checks."""
    match settings.load(repo):
        case Ok(chosen):
            return [
                *(guard.path for guard in chosen.guarded_paths),
                *(pattern for check in chosen.checks for pattern in check.when),
            ]
        case Err():
            return []


def files(repo: Path) -> dict[str, str]:
    """Relative path -> SHA-256 of every code file on disk, and of every file a guarded path or
    a check's `when` glob names."""
    root = repo.resolve()
    chosen, planning, extra = patterns(repo), planning_folder(repo), evidenced(repo)
    found: dict[str, str] = {}
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = sorted(
            d for d in subdirs if not d.startswith(".") and d not in _SKIPPED
        )
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not (
                is_code(relative, chosen, planning=planning)
                or (extra and globs.matches(relative, extra))
            ):
                continue
            try:
                found[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
    return found


def digest(contents: Mapping[str, str]) -> str:
    """One digest for a set of files: any added, removed, or edited file changes it."""
    lines = "".join(f"{path}\0{contents[path]}\n" for path in sorted(contents))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def current(repo: Path) -> str:
    """The digest of the project's code as it is now."""
    return digest(files(repo))


def changed(baseline: Mapping[str, str], now: Mapping[str, str]) -> tuple[str, ...]:
    """Files added, removed, or edited since the baseline."""
    return tuple(
        sorted(
            path
            for path in set(baseline) | set(now)
            if baseline.get(path) != now.get(path)
        )
    )


def save_baseline(folder: Path, work_item: str, contents: Mapping[str, str]) -> None:
    """Remember the code as it was when the work session took up `work_item`."""
    state.write_json(
        folder / BASELINE, {"work_item": work_item, "files": dict(contents)}
    )


def baseline(folder: Path, work_item: str) -> dict[str, str] | None:
    """The code as it was when the session took up `work_item`, or None if never recorded."""
    match state.read_json(folder / BASELINE):
        case {"work_item": str() as linked, "files": dict() as recorded} if (
            linked == work_item
        ):
            return {str(path): str(sha) for path, sha in recorded.items()}
        case _:
            return None


def applicable_checks(chosen: settings.Settings, changed: tuple[str, ...]) -> set[str]:
    """The configured checks whose `when` globs match a changed file, or that have none."""
    return {
        check.name
        for check in chosen.checks
        if not check.when or globs.select(changed, list(check.when))
    }
