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


class TrackerPatternAndGraphTests(unittest.TestCase):
    def test_id_patterns_must_compile(self):
        manifest = _manifest("acme")
        manifest["ids"] = {**manifest["ids"], "pattern": "[A-Z"}
        with self.assertRaisesRegex(TrackerError, "ids.pattern"):
            validate_manifest(manifest)

    def test_id_patterns_cannot_capture(self):
        manifest = _manifest("acme")
        manifest["ids"] = {**manifest["ids"], "branch_key": "([A-Z]+)-[0-9]+"}
        with self.assertRaisesRegex(TrackerError, "ids.branch_key"):
            validate_manifest(manifest)

    def test_a_deep_hierarchy_validates_without_recursion_limits(self):
        manifest = _manifest("acme")
        depth = 3000
        manifest["artifacts"] = [
            {
                "name": f"L{level}",
                "children": [f"L{level + 1}"] if level < depth else [],
            }
            for level in range(depth + 1)
        ]
        manifest["roles"] = {
            "containers": ["L0"],
            "delivery_unit": "L1",
            "step": f"L{depth}",
        }
        self.assertEqual(validate_manifest(manifest)["name"], "acme")

    def test_a_diamond_hierarchy_validates_quickly(self):
        manifest = _manifest("acme")
        levels = 40
        manifest["artifacts"] = [
            *(
                {
                    "name": f"{side}{level}",
                    "children": [f"A{level + 1}", f"B{level + 1}"],
                }
                for level in range(levels)
                for side in "AB"
            ),
            {"name": f"A{levels}", "children": []},
            {"name": f"B{levels}", "children": []},
        ]
        manifest["roles"] = {
            "containers": ["A0"],
            "delivery_unit": "A1",
            "step": f"A{levels}",
        }
        self.assertEqual(validate_manifest(manifest)["name"], "acme")
