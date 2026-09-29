from __future__ import annotations

import unittest

from core.schema import errors

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "tags"],
    "$defs": {"tag": {"type": "string", "minLength": 1, "pattern": "^[a-z]+$"}},
    "properties": {
        "name": {"type": "string"},
        "tags": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"$ref": "#/$defs/tag"},
        },
        "size": {"type": "integer", "minimum": 1, "maximum": 3},
        "kind": {"enum": ["a", "b"]},
        "map": {
            "type": "object",
            "minProperties": 1,
            "propertyNames": {"pattern": "^k"},
            "additionalProperties": {"type": "boolean"},
        },
        "either": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
    },
}


class SchemaTest(unittest.TestCase):
    def test_a_conforming_value_has_no_errors(self) -> None:
        value = {
            "name": "x",
            "tags": ["a", "b"],
            "size": 2,
            "kind": "a",
            "map": {"k1": True},
            "either": 3,
        }
        self.assertEqual(errors(SCHEMA, value), ())

    def test_every_broken_keyword_is_reported_with_its_path(self) -> None:
        value = {
            "tags": ["a", "a", "B"],
            "size": 9,
            "kind": "c",
            "map": {"x": 1},
            "either": True,
            "extra": 1,
        }
        found = "\n".join(errors(SCHEMA, value))
        for fragment in (
            "$: missing 'name'",
            "$.tags: items must be unique",
            "$.tags[2]: must match",
            "$.size: must be at most 3",
            "$.kind: must be one of",
            "$.map['x']: must match",
            "$.map.x: must be boolean",
            "$.either: must match exactly one",
            "$: unexpected 'extra'",
        ):
            self.assertIn(fragment, found)

    def test_booleans_are_not_integers(self) -> None:
        self.assertTrue(errors({"type": "integer"}, True))

    def test_an_unknown_keyword_is_a_schema_defect(self) -> None:
        self.assertEqual(
            errors({"format": "uri"}, "x"),
            ("$: schema uses unsupported keyword 'format'",),
        )
