"""Small helpers shared by the harness CLI modules."""

from __future__ import annotations

import sys
from pathlib import Path

from core.result import Err, Ok, Result
from harness import modes, project_paths


def print_result(result: Result[str]) -> int:
    match result:
        case Ok(text):
            print(text)
            return 0
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2


def resolve_repo(value: str) -> Path:
    return project_paths.root(Path(value))


def pairs(values: list[str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(
        (key.strip(), value.strip())
        for key, _, value in (item.partition("=") for item in values or ())
    )


def read_mode(repo: Path) -> modes.Active | None:
    """The active mode, if any. What the read repaired, or could not repair, is said on stderr, so
    whoever runs the command sees it."""
    read = modes.resolve(repo)
    if read.notice:
        print(read.notice, file=sys.stderr)
    return read.active
