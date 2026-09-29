"""Read loosely typed values: provider replies, which wrap lists and name fields differently from
server to server, and the files people write. Nothing here raises; what cannot be read is absent.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from typing import Any

from core.result import Ok, Result, attempt, err, value_or

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
    "cycles",
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


def is_listing(value: Any) -> bool:
    """Whether a reply is a list, bare or under one of the usual wrapper keys (an empty one counts)."""
    return isinstance(value, list) or (
        isinstance(value, dict)
        and any(isinstance(value.get(key), list) for key in LIST_KEYS)
    )


def readable(reply: Any, *markers: str) -> bool:
    """Whether a reply that was given holds data: a listing, or one record holding any of `markers`."""
    return is_listing(reply) or bool(one_or_many(reply, *markers))


def records(value: Any) -> tuple[Mapping[str, Any], ...]:
    return tuple(item for item in items(value) if isinstance(item, dict))


def one_or_many(value: Any, *markers: str) -> tuple[Mapping[str, Any], ...]:
    """A reply that is one record (it holds any of `markers`) or a list of them, as records."""
    return (
        (value,)
        if isinstance(value, dict) and any(key in value for key in markers)
        else records(value)
    )


def named(
    entries: tuple[Mapping[str, Any], ...], ref: str, *keys: str
) -> Mapping[str, Any] | None:
    """The first entry whose `keys` hold `ref`, compared without case; None when none does."""
    wanted = ref.strip().lower()
    return next(
        (
            entry
            for entry in entries
            if wanted
            and any(str(entry.get(key, "")).strip().lower() == wanted for key in keys)
        ),
        None,
    )


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


def parse_date(value: Any) -> date | None:
    """An ISO date or datetime string as a date; None when there is none to read."""
    text = str(value or "").strip()
    return value_or(
        attempt(lambda: date.fromisoformat(text[:10]), "no_date", text, ValueError)
        if text
        else Ok(None),
        None,
    )


def as_float(value: Any) -> float | None:
    """A finite number from a reply or a file; None when the value is not one (a flag is not, and
    neither is "nan" or "inf")."""
    match value:
        case bool():
            return None
        case int() | float():
            return float(value) if math.isfinite(value) else None
        case str():
            return as_float(
                value_or(
                    attempt(
                        lambda: float(value.strip()), "no_number", value, ValueError
                    ),
                    None,
                )
            )
        case _:
            return None


def first_number(record: Mapping[str, Any], *names: str) -> float | None:
    """The first of `names` holding a number. Not an `or` chain: a real 0 is falsy."""
    return next(
        (
            number
            for number in (as_float(record.get(name)) for name in names)
            if number is not None
        ),
        None,
    )


def as_text(value: Any) -> str:
    """Text or a number as trimmed text; `""` for anything else (an object is not a name)."""
    match value:
        case bool():
            return ""
        case str():
            return value.strip()
        case int() | float():
            return str(value)
        case _:
            return ""


def listed(value: Any) -> tuple[Any, ...]:
    """A JSON list as a tuple; empty for anything else."""
    return tuple(value) if isinstance(value, list) else ()
