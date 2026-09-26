from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.harness import state
from scripts.trackers.registry import available
from tests.harness.test_questions import HOOK, PLAIN, ask, run

NAMED = "Use the acme tracker for this project's work items?"
from tests.trackers.test_registry import _manifest


class TrackerPinningTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness/policy.json").write_text('{"schemaVersion": 1}')
        self.folder = self.repo / ".harness/trackers/acme"
        self.folder.mkdir(parents=True)
        (self.folder / "tracker.json").write_text(
            json.dumps(_manifest("acme")), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def approve(self, text: str, tool_use_id: str) -> dict:
        self.assertIsNone(
            run(self.repo, "ask", {"tool_use_id": tool_use_id, "tool_input": ask(text)})
        )
        answered = {**ask(text), "answers": {text: "Approve"}}
        return run(
            self.repo,
            "answer",
            {
                "tool_use_id": tool_use_id,
                "tool_input": answered,
                "tool_response": answered,
            },
        )

    def prompt(self, text: str) -> None:
        subprocess.run(
            [sys.executable, str(HOOK), "--host", "claude", "--event", "prompt"],
            input=json.dumps({"cwd": str(self.repo), "prompt": text}),
            capture_output=True,
            text=True,
            check=True,
        )

    def names(self) -> list[str]:
        return [tracker.name for tracker in available(self.repo)]

    def test_an_approval_naming_the_tracker_pins_it_and_edits_or_revocation_hide_it(
        self,
    ):
        response = self.approve(NAMED, "toolu_tracker")

        self.assertIn(
            "pins 1 approved onboarded tracker",
            response["hookSpecificOutput"]["additionalContext"],
        )
        self.assertIn("acme", self.names())

        (self.folder / "reference.md").write_text("changed", encoding="utf-8")
        self.assertNotIn("acme", self.names())

        state.revoke_approvals(self.repo)
        self.assertNotIn("acme", self.names())

    def test_an_unrelated_approval_does_not_pin_the_tracker(self):
        response = self.approve(PLAIN, "toolu_other")

        self.assertNotIn("pins", response["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("acme", self.names())

    def test_a_typed_approval_pins_only_when_it_names_the_tracker(self):
        self.prompt("approve HB-AAAA1")
        self.assertNotIn("acme", self.names())
        self.prompt("approve HB-BBBB2 and the acme tracker")
        self.assertIn("acme", self.names())

    def test_a_broken_onboarded_manifest_hides_only_itself(self):
        self.approve(NAMED, "toolu_tracker")
        junk = self.repo / ".harness/trackers/junk"
        junk.mkdir()
        (junk / "tracker.json").write_text("{", encoding="utf-8")
        self.assertIn("acme", self.names())
        self.assertIn("linear", self.names())


if __name__ == "__main__":
    unittest.main()
