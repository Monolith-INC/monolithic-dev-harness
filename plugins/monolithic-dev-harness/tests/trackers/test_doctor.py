"""`harness doctor` says which tracker is chosen, whether it loads, and what each onboarded folder is."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.trackers.registry import onboarded_status, pin_approved_trackers

from .test_registry import _manifest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts" / "harness" / "cli.py"


class TrackerDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness/policy.json").write_text('{"schemaVersion": 1}')

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def choose(self, tracker: object) -> None:
        (self.repo / ".harness/integrations.json").write_text(
            json.dumps({"schemaVersion": 1, "tracker": tracker})
        )

    def onboard(self, name: str, status: str = "approved") -> Path:
        folder = self.repo / ".harness/trackers" / name
        folder.mkdir(parents=True)
        (folder / "tracker.json").write_text(
            json.dumps({**_manifest(name), "status": status})
        )
        return folder

    def doctor(self) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, str(CLI), "doctor", "--repo", str(self.repo)],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout

    def tracker_lines(self) -> str:
        return self.doctor()[1].split("Tracker\n", 1)[1]

    def test_no_tracker_chosen_is_reported_not_failed(self):
        self.assertIn("[skip] tracker — none chosen", self.tracker_lines())

    def test_a_shipped_tracker_that_loads_is_ok(self):
        self.choose({"name": "linear"})
        self.assertIn("[  ok] tracker — linear (shipped)", self.tracker_lines())

    def test_a_tracker_that_cannot_load_fails_and_says_mcp_is_blocked(self):
        self.choose({"name": "missing"})
        code, output = self.doctor()
        lines = output.split("Tracker\n", 1)[1]
        self.assertIn("[FAIL] tracker — ", lines)
        self.assertIn("'missing'", lines)
        self.assertIn("MCP calls are blocked", lines)
        self.assertEqual(code, 1)

    def test_an_unreadable_choice_fails(self):
        (self.repo / ".harness/integrations.json").write_text("{")
        self.assertIn("[FAIL] tracker — could not read", self.tracker_lines())

    def test_each_onboarded_folder_reports_its_state(self):
        self.onboard("drafty", status="draft")
        self.onboard("waiting")
        pin_approved_trackers(self.repo, "approval", ())
        broken = self.repo / ".harness/trackers/broken"
        broken.mkdir(parents=True)
        (broken / "tracker.json").write_text("{")
        lines = self.tracker_lines()
        self.assertIn("[skip] onboarded drafty — draft", lines)
        self.assertIn("[warn] onboarded waiting — approved but not pinned", lines)
        self.assertIn("[warn] onboarded broken — invalid", lines)

    def test_onboarded_status_marks_a_pinned_folder(self):
        from scripts.harness import state

        folder = self.onboard("acme")
        state.open_approval(self.repo, "HB-TEST1", 20)
        pin_approved_trackers(self.repo, "HB-TEST1", (folder,))
        self.assertEqual(
            [(item.folder.name, item.state) for item in onboarded_status(self.repo)],
            [("acme", "pinned")],
        )


if __name__ == "__main__":
    unittest.main()
