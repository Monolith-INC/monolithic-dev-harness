"""The standard-library schema check agrees with JSON Schema and keeps hooks dependency free."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.trackers import schema_check
from scripts.trackers.registry import (
    DEFAULT_SHIPPED_ROOT,
    SCHEMA_PATH,
    TrackerError,
    validate_manifest,
)

from .test_registry import _manifest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _mutations() -> dict[str, dict[str, object]]:
    def changed(edit) -> dict[str, object]:
        manifest = copy.deepcopy(_manifest("acme"))
        edit(manifest)
        return manifest

    return {
        "missing field": changed(lambda m: m.pop("writes")),
        "boolean schema version": changed(lambda m: m.update(schemaVersion=True)),
        "wrong schema version": changed(lambda m: m.update(schemaVersion=2)),
        "name breaks pattern": changed(lambda m: m.update(name="Acme")),
        "empty label": changed(lambda m: m.update(label="")),
        "unknown top-level key": changed(lambda m: m.update(extra=1)),
        "unknown access kind": changed(lambda m: m["access"].update(kind="smtp")),
        "extra access key": changed(lambda m: m["access"].update(token="x")),
        "no artifacts": changed(lambda m: m.update(artifacts=[])),
        "artifact child not a string": changed(
            lambda m: m["artifacts"][0].update(children=[1])
        ),
        "setting key breaks pattern": changed(
            lambda m: m.update(settings=[{"key": "1bad", "required": True}])
        ),
        "setting required not boolean": changed(
            lambda m: m.update(settings=[{"key": "org", "required": "yes"}])
        ),
        "missing state": changed(lambda m: m["states"].pop("done")),
        "unknown ids key": changed(lambda m: m["ids"].update(links=True)),
        "attachment value empty": changed(lambda m: m["attachments"].update(spec="")),
        "no sources": changed(lambda m: m.update(sources={})),
        "bad text format": changed(lambda m: m.update(text_format="rtf")),
        "manifest not an object": [],  # type: ignore[dict-item]
    }


def _shipped() -> dict[str, object]:
    return {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(DEFAULT_SHIPPED_ROOT.glob("*/tracker.json"))
    }


class SchemaCheckTests(unittest.TestCase):
    def test_the_tracker_schema_uses_only_supported_keywords(self):
        self.assertEqual(schema_check.unsupported(SCHEMA), frozenset())

    def test_unsupported_keywords_are_found_at_any_depth(self):
        schema = {"properties": {"a": {"items": {"oneOf": []}}}, "allOf": []}
        self.assertEqual(schema_check.unsupported(schema), {"oneOf", "allOf"})

    def test_shipped_and_fixture_manifests_pass(self):
        for name, manifest in {**_shipped(), "fixture": _manifest("acme")}.items():
            with self.subTest(name=name):
                self.assertEqual(list(schema_check.errors(manifest, SCHEMA)), [])

    def test_every_mutation_is_rejected_by_the_registry(self):
        for name, manifest in _mutations().items():
            with self.subTest(name=name), self.assertRaises(TrackerError):
                validate_manifest(manifest)

    def test_error_names_the_field_that_broke(self):
        manifest = _manifest("acme")
        manifest["access"] = {**manifest["access"], "kind": "smtp"}
        with self.assertRaisesRegex(TrackerError, "access.kind"):
            validate_manifest(manifest)

    def test_verdicts_match_jsonschema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is a development-only dependency")
        validator = jsonschema.Draft202012Validator(SCHEMA)
        cases = {**_shipped(), "fixture": _manifest("acme"), **_mutations()}
        for name, manifest in cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    validator.is_valid(manifest),
                    not list(schema_check.errors(manifest, SCHEMA)),
                )

    def test_the_registry_loads_without_jsonschema(self):
        blocker = (
            "import sys; sys.modules['jsonschema'] = None; "
            "from trackers.registry import validate_manifest, DEFAULT_SHIPPED_ROOT; "
            "import json; "
            "[validate_manifest(json.loads(p.read_text())) "
            "for p in DEFAULT_SHIPPED_ROOT.glob('*/tracker.json')]"
        )
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            cwd=PLUGIN_ROOT,
            env={**os.environ, "PYTHONPATH": "scripts"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
