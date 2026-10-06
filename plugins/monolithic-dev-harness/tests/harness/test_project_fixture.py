from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY))

from core.result import Err, Ok  # noqa: E402
from tools.project_fixture import (  # noqa: E402
    create_test_project,
    discard_test_project,
)


class ProjectFixtureTests(unittest.TestCase):
    def test_missing_configuration_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = create_test_project(Path(directory) / "missing.json")

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "missing_configuration")

    def test_invalid_json_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text("{", encoding="utf-8")

            result = create_test_project(configuration)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "invalid_configuration_json")

    def test_non_object_json_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text("[]", encoding="utf-8")

            result = create_test_project(configuration)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "invalid_configuration")

    def test_schema_invalid_configuration_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text(json.dumps({"tracker": {"name": "local"}}))

            result = create_test_project(configuration)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "invalid_settings")

    def test_valid_configuration_creates_configured_copy_that_can_be_discarded(self):
        settings = {
            "schemaVersion": 1,
            "tracker": {"name": "local"},
            "scm": {"name": "local"},
            "branch_template": "{key}-{slug}",
            "artifacts_path": "docs/planning",
        }
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text(json.dumps(settings), encoding="utf-8")

            result = create_test_project(configuration)

        self.assertIsInstance(result, Ok)
        project = result.value
        try:
            self.assertEqual(project.parent.parent, REPOSITORY / "temp")
            self.assertTrue(project.parent.name.startswith("test-"))
            applied = json.loads((project / ".harness/settings.json").read_text())
            self.assertEqual(applied, settings)
            self.assertTrue((project / "README.md").is_file())
            self.assertTrue((project / "_bmad/config.toml").is_file())
            self.assertTrue((project / "_bmad/scripts").is_dir())
            self.assertIn(
                "{project-root}/docs/planning",
                (project / "_bmad/custom/config.toml").read_text(),
            )
            self.assertTrue((project / ".harness/tracker/backlog").is_dir())
        finally:
            discarded = discard_test_project(project)

        self.assertIsInstance(discarded, Ok)
        self.assertFalse(project.parent.exists())

    def test_new_fixture_removes_abandoned_test_run_copies(self):
        from acceptance_trial import MARKER_NAME, RUN_PREFIX, prepare

        abandoned = prepare(root_prefix=RUN_PREFIX, kind="run")
        marker_path = abandoned.parent / MARKER_NAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["process_id"] = 2**30
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        configuration = {
            "schemaVersion": 1,
            "tracker": {"name": "local"},
            "scm": {"name": "local"},
            "branch_template": "{key}-{slug}",
        }

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text(json.dumps(configuration), encoding="utf-8")
            result = create_test_project(config_path)

        self.assertIsInstance(result, Ok)
        self.assertFalse(abandoned.parent.exists())
        discard_test_project(result.value)

    def test_each_call_returns_a_fresh_copy(self):
        settings = {
            "schemaVersion": 1,
            "tracker": {"name": "local"},
            "scm": {"name": "local"},
            "branch_template": "{key}-{slug}",
        }
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text(json.dumps(settings), encoding="utf-8")
            first = create_test_project(configuration)
            second = create_test_project(configuration)

        self.assertIsInstance(first, Ok)
        self.assertIsInstance(second, Ok)
        self.assertNotEqual(first.value, second.value)
        discard_test_project(first.value)
        discard_test_project(second.value)


if __name__ == "__main__":
    unittest.main()
