from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.harness import state
from scripts.trackers.registry import available
from tests.harness.test_questions import PLAIN, ask, run
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

    def test_approve_click_pins_an_onboarded_tracker_and_edits_or_revocation_hide_it(
        self,
    ):
        self.assertIsNone(
            run(self.repo, "ask", {"tool_use_id": "toolu_tracker", "tool_input": ask()})
        )
        response = run(
            self.repo,
            "answer",
            {
                "tool_use_id": "toolu_tracker",
                "tool_input": {**ask(), "answers": {PLAIN: "Approve"}},
                "tool_response": {**ask(), "answers": {PLAIN: "Approve"}},
            },
        )

        self.assertIn(
            "pins 1 approved onboarded tracker",
            response["hookSpecificOutput"]["additionalContext"],
        )
        self.assertIn("acme", [tracker.name for tracker in available(self.repo)])

        (self.folder / "reference.md").write_text("changed", encoding="utf-8")
        self.assertNotIn("acme", [tracker.name for tracker in available(self.repo)])

        state.revoke_approvals(self.repo)
        self.assertNotIn("acme", [tracker.name for tracker in available(self.repo)])


if __name__ == "__main__":
    unittest.main()
