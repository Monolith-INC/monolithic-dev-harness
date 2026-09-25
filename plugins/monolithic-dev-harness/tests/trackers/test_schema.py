from __future__ import annotations

import unittest

from scripts.trackers.registry import TrackerError, validate_manifest

from .test_registry import _manifest


class TrackerSchemaTests(unittest.TestCase):
    def test_valid_manifest_passes_schema_and_domain_validation(self):
        self.assertEqual(validate_manifest(_manifest("acme"))["name"], "acme")

    def test_schema_error_names_the_missing_field(self):
        manifest = _manifest("acme")
        manifest.pop("writes")

        with self.assertRaisesRegex(TrackerError, "writes"):
            validate_manifest(manifest)

    def test_role_must_name_a_declared_artifact(self):
        manifest = _manifest("acme")
        manifest["roles"] = {**manifest["roles"], "step": "Missing"}

        with self.assertRaisesRegex(TrackerError, "roles.step"):
            validate_manifest(manifest)

    def test_artifact_hierarchy_cannot_contain_a_cycle(self):
        manifest = _manifest("acme")
        manifest["artifacts"] = [
            {"name": "Feature", "children": ["Story"]},
            {"name": "Story", "children": ["Feature"]},
            {"name": "Task", "children": []},
        ]

        with self.assertRaisesRegex(TrackerError, "artifacts"):
            validate_manifest(manifest)
