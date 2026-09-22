"""Repository-relative glob matching with `**` support (Python 3.10+ compatible)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def normalize(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def matches(path: str, patterns: Iterable[str]) -> bool:
    candidate = normalize(path)
    return any(_compile(normalize(p)).match(candidate) for p in patterns)


def select(
    paths: Iterable[str], include: Iterable[str], exclude: Iterable[str] = ()
) -> list[str]:
    include = list(include)
    exclude = list(exclude)
    return [p for p in paths if matches(p, include) and not matches(p, exclude)]
