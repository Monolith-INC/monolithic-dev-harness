"""The project's code as content, never as version control.

Which files are code (the settings' source and test globs, outside the planning folder, plus the
files guarded paths and check triggers name), a digest per file, one digest for all of them, and
what changed since a work item was first linked. Check, review, and manual-check evidence is keyed
to that one digest, so it describes exactly the code on disk and any later change invalidates it,
whether or not the project uses Git.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from core.result import Err, Ok
from harness import globs, local_artifacts, settings, state
from policy.commands import is_code

BASELINES = "code-baselines"
# Folders never walked: hidden ones (.git, .harness, tool caches) and dependency stores.
_SKIPPED = frozenset({"node_modules", "__pycache__"})
# With no source or test globs every file counts as code, except what builds and test runs write:
# a check that leaves output there must not change the code it just checked.
_OUTPUTS = frozenset({"build", "dist", "out", "target", "coverage"})


@dataclass(frozen=True)
class Selection:
    """Which files count, read once from the settings."""

    code: list[str] | None  # source and test globs; None means every file
    evidenced: list[str]  # guarded paths and the globs that trigger checks
    planning: str  # the artifacts path inside the project, never code when Markdown

    def counts(self, relative: str) -> bool:
        return is_code(relative, self.code, planning=self.planning) or (
            bool(self.evidenced) and globs.matches(relative, self.evidenced)
        )


def selection(repo: Path) -> Selection:
    match settings.load(repo):
        case Ok(chosen):
            code = [
                pattern
                for group in chosen.tests_required
                for pattern in (*group.source, *group.tests)
            ]
            evidenced = [
                *(guard.path for guard in chosen.guarded_paths),
                *(pattern for check in chosen.checks for pattern in check.when),
            ]
            return Selection(code or None, evidenced, planning_folder(repo))
        case Err():
            return Selection(None, [], planning_folder(repo))


def patterns(repo: Path) -> list[str] | None:
    """The settings' source and test globs, or None (every file is code) when they name none."""
    return selection(repo).code


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


def files(repo: Path) -> dict[str, str]:
    """Relative path -> SHA-256 of every file that counts (see `Selection`)."""
    root = repo.resolve()
    chosen = selection(repo)
    skipped = _SKIPPED | (_OUTPUTS if chosen.code is None else frozenset())
    found: dict[str, str] = {}
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = sorted(
            d for d in subdirs if not d.startswith(".") and d not in skipped
        )
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not chosen.counts(relative):
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


def _baseline_path(repo: Path, work_item: str) -> Path:
    return (
        state.state_dir(repo) / BASELINES / f"{state.safe_name(work_item.upper())}.json"
    )


def record_baseline(repo: Path, work_item: str) -> None:
    """Remember the code as it was when `work_item` was first linked, once per project.

    Linking it again, from any work session, keeps the first record, so no relink hides a change.
    """
    path = _baseline_path(repo, work_item)
    if state.read_json(path) is None:
        state.write_json(path, {"work_item": work_item, "files": files(repo)})


def baseline(repo: Path, work_item: str) -> dict[str, str] | None:
    """The code as it was when `work_item` was first linked, or None if never recorded."""
    match state.read_json(_baseline_path(repo, work_item)):
        case {"files": dict() as recorded}:
            return {str(path): str(sha) for path, sha in recorded.items()}
        case _:
            return None


def changed_since_link(
    repo: Path, work_session_id: str | None, now: Mapping[str, str]
) -> tuple[str, ...]:
    """Files changed since the session's work item was first linked; all of them when unknown."""
    from harness import work_sessions

    match work_session_id and work_sessions.select(repo, work_session_id):
        case Ok(session) if session.work_item:
            recorded = baseline(repo, session.work_item)
        case _:
            recorded = None
    return tuple(sorted(now)) if recorded is None else changed(recorded, now)


def applicable_checks(chosen: settings.Settings, changed: tuple[str, ...]) -> set[str]:
    """The configured checks whose `when` globs match a changed file, or that have none."""
    return {
        check.name
        for check in chosen.checks
        if not check.when or globs.select(changed, list(check.when))
    }
