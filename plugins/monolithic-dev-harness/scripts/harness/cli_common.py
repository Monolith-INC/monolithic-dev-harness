"""Small helpers shared by the harness CLI modules."""

from __future__ import annotations

import sys
from pathlib import Path

from core.result import Err, Ok, Result
from harness import gitstate


def print_result(result: Result[str]) -> int:
    match result:
        case Ok(text):
            print(text)
            return 0
        case Err(failure):
            print(failure.message, file=sys.stderr)
            return 2


def resolve_repo(value: str) -> Path:
    return gitstate.repo_root(Path(value)) or Path(value).resolve()


def pairs(values: list[str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(
        (key.strip(), value.strip())
        for key, _, value in (item.partition("=") for item in values or ())
    )
