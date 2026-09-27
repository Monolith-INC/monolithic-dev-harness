"""Read provider replies, which wrap lists and name fields differently from server to server."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.result import Ok, Result, err

LIST_KEYS = (
    "items",
    "nodes",
    "value",
    "workItems",
    "artifacts",
    "threads",
    "comments",
    "issues",
    "teamMembers",
    "iterations",
    "values",
)


def items(value: Any) -> tuple[Any, ...]:
    """The list a reply carries, bare or under one of the usual wrapper keys."""
    match value:
        case list():
            return tuple(value)
        case dict():
            return next(
                (
                    tuple(value[key])
                    for key in LIST_KEYS
                    if isinstance(value.get(key), list)
                ),
                (),
            )
        case _:
            return ()


def records(value: Any) -> tuple[Mapping[str, Any], ...]:
    return tuple(item for item in items(value) if isinstance(item, dict))


def text(value: Mapping[str, Any], *keys: str) -> str:
    """The first of `keys` that holds a value, as text; `""` when none does."""
    return next(
        (str(value[key]) for key in keys if value.get(key) not in (None, "")), ""
    )


def number(ref: str | int, what: str) -> Result[int]:
    digits = str(ref).strip().lstrip("#")
    return (
        Ok(int(digits))
        if digits.isdigit()
        else err("invalid_request", f"{what} must be a numeric id, got {ref!r}")
    )


def reverse(mapping: Mapping[Any, str], provider_value: str, fallback: Any) -> Any:
    """The harness value a provider value maps back to, compared without case or spacing."""
    wanted = normalized(provider_value)
    return next(
        (logical for logical, name in mapping.items() if normalized(name) == wanted),
        fallback,
    )


def normalized(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def mapping(reply: Any) -> Mapping[str, Any]:
    return reply if isinstance(reply, dict) else {"result": reply}


def object_or_empty(value: Any) -> Mapping[str, Any]:
    """A nested object from a reply, or an empty one when the reply holds something else there."""
    return value if isinstance(value, dict) else {}
