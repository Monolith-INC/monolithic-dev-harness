"""Bounded reuse of pure shell parsing; never cache filesystem reads or policy decisions."""

from collections.abc import Callable
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=64)
def _parsed(
    parser: Callable, command: str, cwd: str | None, depth: int
) -> tuple[Any, ...]:
    return tuple(parser(command, cwd, depth))


def parse(parser: Callable, command: str, cwd: str | None, depth: int) -> list[Any]:
    match len(command) <= 65_536:
        case True:
            return list(_parsed(parser, command, cwd, depth))
        case False:
            return parser(command, cwd, depth)
