from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from core.result import Ok  # noqa: E402
from harness import settings  # noqa: E402

MINIMAL = {
    "schemaVersion": 1,
    "tracker": {"name": "local"},
    "scm": {"name": "github", "values": {"owner": "o", "repo": "r"}},
    "branch_template": "feature/{key}-{slug}",
}


class SettingsTest(unittest.TestCase):
    def test_omitted_sections_take_their_defaults(self) -> None:
        loaded = settings.parse(MINIMAL).value
        self.assertEqual(
            (loaded.base_branch, loaded.approval_minutes, loaded.require_draft),
            ("develop", 20, True),
        )
        self.assertEqual(
            (loaded.tracker.source, loaded.protected_work_items),
            ("shipped", frozenset()),
        )

    def test_the_schema_and_the_cross_checks_reject_bad_files(self) -> None:
        cases = {
            "unknown section": {**MINIMAL, "azure": {}},
            "no key in template": {**MINIMAL, "branch_template": "feature/x"},
            "unknown scm": {**MINIMAL, "scm": {"name": "gitlab"}},
            "guard names no check": {
                **MINIMAL,
                "guarded_paths": [{"path": "a", "evidence": "check:unit"}],
            },
            "bad evidence": {
                **MINIMAL,
                "guarded_paths": [{"path": "a", "evidence": "trust:me"}],
            },
        }
        for label, value in cases.items():
            self.assertNotIsInstance(settings.parse(value), Ok, label)

    def test_the_file_is_what_opts_a_repository_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertFalse(settings.governed(repo))
            (repo / ".harness").mkdir()
            (repo / ".harness" / "settings.json").write_text(
                json.dumps({**MINIMAL, "protected_work_items": ["1001"]})
            )
            self.assertTrue(settings.governed(repo))
            self.assertEqual(
                settings.load(repo).value.protected_work_items, frozenset({"1001"})
            )
            (repo / ".harness" / "settings.json").write_text("{")
            self.assertEqual(settings.load(repo).failure.code, "invalid_settings")

    def test_the_example_settings_are_valid(self) -> None:
        example = (
            Path(__file__).resolve().parents[2] / "examples" / "settings.example.json"
        )
        self.assertIsInstance(settings.parse(json.loads(example.read_text())), Ok)
