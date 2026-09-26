"""Check a JSON value against a JSON Schema, with the standard library only.

The hooks run before every tool call and may not depend on third-party packages, so this covers the
subset of JSON Schema 2020-12 the harness schemas use: `type`, `const`, `enum`, `required`,
`properties`, `additionalProperties`, `propertyNames`, `items`, `minItems`, `uniqueItems`,
`minProperties`, `minLength`, `pattern`, `minimum`, `maximum`, `$defs` with local `$ref`, and
`oneOf`. An unknown keyword is a schema defect, reported as one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err

_TYPES: Mapping[str, Callable[[Any], bool]] = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "boolean": lambda value: isinstance(value, bool),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    ),
}
_ANNOTATIONS = frozenset({"$schema", "$id", "title", "description", "$defs", "default"})


def errors(schema: Mapping[str, Any], value: Any) -> tuple[str, ...]:
    """Every way `value` breaks `schema`, as `path: message` lines; empty when it conforms."""
    return _check(schema, schema, value, "$")


def validate(schema: Mapping[str, Any], value: Any, what: str) -> Result[Any]:
    found = errors(schema, value)
    return (
        Ok(value)
        if not found
        else err("invalid_" + what, f"{what}: " + "; ".join(found))
    )


@lru_cache(maxsize=8)
def _load(path: Path) -> Result[Mapping[str, Any]]:
    return attempt(
        lambda: json.loads(path.read_text(encoding="utf-8")),
        "schema_unreadable",
        f"could not read schema {path.name}",
        OSError,
        ValueError,
    )


def load_schema(path: Path) -> Result[Mapping[str, Any]]:
    return bind(
        _load(path),
        lambda schema: (
            Ok(schema)
            if isinstance(schema, dict)
            else err("schema_unreadable", f"{path.name} is not an object")
        ),
    )


def _check(
    root: Mapping[str, Any], schema: Mapping[str, Any], value: Any, path: str
) -> tuple[str, ...]:
    return tuple(
        problem
        for keyword, argument in schema.items()
        if keyword not in _ANNOTATIONS
        for problem in _keyword(root, schema, keyword, argument, value, path)
    )


def _keyword(
    root: Mapping[str, Any],
    schema: Mapping[str, Any],
    keyword: str,
    argument: Any,
    value: Any,
    path: str,
) -> tuple[str, ...]:
    match keyword:
        case "$ref":
            return _check(root, _resolve(root, str(argument)), value, path)
        case "type":
            return (
                () if _TYPES[str(argument)](value) else (f"{path}: must be {argument}",)
            )
        case "const":
            return (
                ()
                if value == argument
                else (f"{path}: must be {json.dumps(argument)}",)
            )
        case "enum":
            return (
                ()
                if value in argument
                else (f"{path}: must be one of {json.dumps(argument)}",)
            )
        case "oneOf":
            return _one_of(root, argument, value, path)
        case "required":
            return tuple(
                f"{path}: missing {key!r}"
                for key in argument
                if isinstance(value, dict) and key not in value
            )
        case "properties":
            return tuple(
                problem
                for key, sub in argument.items()
                if isinstance(value, dict) and key in value
                for problem in _check(root, sub, value[key], f"{path}.{key}")
            )
        case "additionalProperties":
            return _additional(root, schema, argument, value, path)
        case "propertyNames":
            return tuple(
                problem
                for key in (value if isinstance(value, dict) else {})
                for problem in _check(root, argument, key, f"{path}[{key!r}]")
            )
        case "minProperties":
            return (
                (f"{path}: needs at least {argument} entries",)
                if isinstance(value, dict) and len(value) < argument
                else ()
            )
        case "items":
            return tuple(
                problem
                for index, item in enumerate(value if isinstance(value, list) else [])
                for problem in _check(root, argument, item, f"{path}[{index}]")
            )
        case "minItems":
            return (
                (f"{path}: needs at least {argument} items",)
                if isinstance(value, list) and len(value) < argument
                else ()
            )
        case "uniqueItems":
            return (
                (f"{path}: items must be unique",)
                if argument
                and isinstance(value, list)
                and len({json.dumps(item, sort_keys=True) for item in value})
                != len(value)
                else ()
            )
        case "minLength":
            return (
                (f"{path}: must not be shorter than {argument}",)
                if isinstance(value, str) and len(value) < argument
                else ()
            )
        case "pattern":
            return (
                (f"{path}: must match {argument}",)
                if isinstance(value, str) and re.search(str(argument), value) is None
                else ()
            )
        case "minimum":
            return (
                (f"{path}: must be at least {argument}",)
                if _TYPES["number"](value) and value < argument
                else ()
            )
        case "maximum":
            return (
                (f"{path}: must be at most {argument}",)
                if _TYPES["number"](value) and value > argument
                else ()
            )
        case _:
            return (f"{path}: schema uses unsupported keyword {keyword!r}",)


def _additional(
    root: Mapping[str, Any],
    schema: Mapping[str, Any],
    argument: Any,
    value: Any,
    path: str,
) -> tuple[str, ...]:
    extra = tuple(
        key
        for key in (value if isinstance(value, dict) else {})
        if key not in schema.get("properties", {})
    )
    match argument:
        case False:
            return tuple(f"{path}: unexpected {key!r}" for key in extra)
        case True:
            return ()
        case _:
            return tuple(
                problem
                for key in extra
                for problem in _check(root, argument, value[key], f"{path}.{key}")
            )


def _one_of(
    root: Mapping[str, Any], options: list[Any], value: Any, path: str
) -> tuple[str, ...]:
    matching = tuple(
        option for option in options if not _check(root, option, value, path)
    )
    return (
        ()
        if len(matching) == 1
        else (f"{path}: must match exactly one allowed shape, matched {len(matching)}",)
    )


def _resolve(root: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    name = reference.removeprefix("#/$defs/")
    return root.get("$defs", {}).get(name, {"const": f"<unresolved {reference}>"})
