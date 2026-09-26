from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.trackers.onboarding import approve, main, stage
from scripts.trackers.registry import TrackerError, validate_manifest
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


class OnboardingNameTests(unittest.TestCase):
    def test_approve_rejects_a_name_that_leaves_the_tracker_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(TrackerError, "not a tracker name"):
                approve(Path(tmp), "../policy")

    def test_a_name_with_a_trailing_newline_is_invalid(self):
        with self.assertRaisesRegex(TrackerError, "name"):
            validate_manifest(_manifest("acme\n"))

    def test_the_command_line_stages_and_approves(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, source = Path(tmp) / "repo", Path(tmp) / "source"
            repo.mkdir()
            source.mkdir()
            (source / "tracker.json").write_text(json.dumps(_manifest("acme")))
            self.assertEqual(main(["stage", str(source), "--repo", str(repo)]), 0)
            self.assertEqual(main(["approve", "acme", "--repo", str(repo)]), 0)
            staged = repo / ".harness/trackers/acme/tracker.json"
            self.assertEqual(json.loads(staged.read_text())["status"], "approved")
            self.assertEqual(main(["approve", "missing", "--repo", str(repo)]), 1)
