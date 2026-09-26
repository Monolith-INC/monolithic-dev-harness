from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.trackers.onboarding import approve, stage
from scripts.trackers.registry import TrackerError
from tests.trackers.test_registry import _manifest


class OnboardingTests(unittest.TestCase):
    def test_stage_requires_approval_before_selectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, source = Path(tmp) / "repo", Path(tmp) / "source"
            repo.mkdir()
            source.mkdir()
            (source / "tracker.json").write_text(json.dumps(_manifest("acme")))
            staged = stage(repo, source)
            self.assertEqual(
                json.loads((staged / "tracker.json").read_text())["status"], "draft"
            )
            self.assertEqual(approve(repo, "acme"), staged)

    def test_stage_rejects_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, source = Path(tmp) / "repo", Path(tmp) / "source"
            repo.mkdir()
            source.mkdir()
            (source / "tracker.json").write_text("{}")
            with self.assertRaises(TrackerError):
                stage(repo, source)


if __name__ == "__main__":
    unittest.main()
