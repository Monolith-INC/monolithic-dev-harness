"""Standard-library check of a value against the JSON Schema subset tracker manifests use.

Hooks load the tracker registry, and hooks run on the standard library only, so the manifest
schema is checked here instead of through `jsonschema`. Only the keywords in `SUPPORTED` are
understood; `unsupported` names any other keyword so a schema that outgrows this checker fails
loudly instead of being half-applied.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

ANNOTATIONS = frozenset({"$schema", "$id", "title", "description"})
SUPPORTED = ANNOTATIONS | frozenset(
    {
        "type",
        "const",
        "enum",
        "pattern",
        "minLength",
        "minItems",
        "minProperties",
        "required",
        "properties",
        "additionalProperties",
        "items",
    }
)

_TYPES: Mapping[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "boolean": (bool,),
    "integer": (int,),
    "number": (int, float),
    "null": (type(None),),
}


@dataclass(frozen=True)
class SchemaError:
    path: tuple[str | int, ...]
    keyword: str
    message: str


def unsupported(schema: Any) -> frozenset[str]:
    """Keywords anywhere in `schema` that this checker does not understand."""
    match schema:
        case dict():
            return (frozenset(schema) - SUPPORTED).union(
                *(unsupported(child) for child in _subschemas(schema))
            )
        case _:
            return frozenset()


def _subschemas(schema: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        *schema.get("properties", {}).values(),
        *(
            (schema["additionalProperties"],)
            if isinstance(schema.get("additionalProperties"), dict)
            else ()
        ),
        *((schema["items"],) if "items" in schema else ()),
    )


def errors(
    value: Any, schema: Mapping[str, Any], path: tuple[str | int, ...] = ()
) -> Iterator[SchemaError]:
    """Every way `value` breaks `schema`; nested checks run only on well-typed values."""
    typed = "type" not in schema or _is_type(value, schema["type"])
    yield from _scalar_errors(value, schema, path, typed)
    yield from (_nested_errors(value, schema, path) if typed else ())


def _scalar_errors(
    value: Any, schema: Mapping[str, Any], path: tuple[str | int, ...], typed: bool
) -> Iterator[SchemaError]:
    checks = (
        ("type", not typed, f"{value!r} is not of type {schema.get('type')!r}"),
        (
            "const",
            "const" in schema and not _equal(value, schema.get("const")),
            f"{schema.get('const')!r} was expected",
        ),
        (
            "enum",
            "enum" in schema
            and not any(_equal(value, option) for option in schema.get("enum", ())),
            f"{value!r} is not one of {schema.get('enum')!r}",
        ),
    )
    return (
        SchemaError(path, keyword, message)
        for keyword, failed, message in checks
        if failed
    )


def _nested_errors(
    value: Any, schema: Mapping[str, Any], path: tuple[str | int, ...]
) -> Iterator[SchemaError]:
    match value:
        case str():
            return _string_errors(value, schema, path)
        case list():
            return _array_errors(value, schema, path)
        case dict():
            return _object_errors(value, schema, path)
        case _:
            return iter(())


def _string_errors(
    value: str, schema: Mapping[str, Any], path: tuple[str | int, ...]
) -> Iterator[SchemaError]:
    checks = (
        (
            "minLength",
            len(value) < schema.get("minLength", 0),
            f"{value!r} is shorter than {schema.get('minLength')}",
        ),
        (
            "pattern",
            "pattern" in schema and re.search(schema["pattern"], value) is None,
            f"{value!r} does not match {schema.get('pattern')!r}",
        ),
    )
    return (
        SchemaError(path, keyword, message)
        for keyword, failed, message in checks
        if failed
    )


def _array_errors(
    value: list[Any], schema: Mapping[str, Any], path: tuple[str | int, ...]
) -> Iterator[SchemaError]:
    too_short = (
        (
            SchemaError(
                path, "minItems", f"should have at least {schema['minItems']} item(s)"
            ),
        )
        if len(value) < schema.get("minItems", 0)
        else ()
    )
    items = (
        error
        for index, item in enumerate(value)
        if "items" in schema
        for error in errors(item, schema["items"], (*path, index))
    )
    return iter((*too_short, *items))


def _object_errors(
    value: dict[str, Any], schema: Mapping[str, Any], path: tuple[str | int, ...]
) -> Iterator[SchemaError]:
    properties = schema.get("properties", {})
    extra = schema.get("additionalProperties", True)
    missing = (
        SchemaError(path, "required", f"{name!r} is a required property")
        for name in schema.get("required", ())
        if name not in value
    )
    too_few = (
        (
            SchemaError(
                path,
                "minProperties",
                f"should have at least {schema['minProperties']} propert(ies)",
            ),
        )
        if len(value) < schema.get("minProperties", 0)
        else ()
    )
    declared = (
        error
        for name, item in value.items()
        if name in properties
        for error in errors(item, properties[name], (*path, name))
    )
    undeclared = (
        error
        for name, item in value.items()
        if name not in properties
        for error in (
            (
                SchemaError(
                    (*path, name),
                    "additionalProperties",
                    f"additional property {name!r} is not allowed",
                ),
            )
            if extra is False
            else errors(item, extra, (*path, name))
            if isinstance(extra, dict)
            else ()
        )
    )
    return iter((*missing, *too_few, *declared, *undeclared))


def _is_type(value: Any, expected: str | list[str]) -> bool:
    names = (expected,) if isinstance(expected, str) else tuple(expected)
    return any(
        isinstance(value, _TYPES[name])
        and not (isinstance(value, bool) and name in {"integer", "number"})
        for name in names
    )


def _equal(left: Any, right: Any) -> bool:
    """JSON equality: `true` is not `1`, unlike Python's `True == 1`."""
    return isinstance(left, bool) == isinstance(right, bool) and left == right
