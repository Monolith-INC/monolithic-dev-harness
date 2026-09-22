"""Cursor failClosed requires allow decisions to emit JSON permission responses."""

from __future__ import annotations

import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import hook_runtime


class TestCursorEmitDecision(unittest.TestCase):
    def test_cursor_allow_emits_permission_json(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            hook_runtime.emit_decision("cursor", hook_runtime.PolicyDecision.allow())

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload, {"permission": "allow"})

    def test_cursor_deny_emits_permission_json(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            hook_runtime.emit_decision(
                "cursor",
                hook_runtime.PolicyDecision.deny("blocked for test"),
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["permission"], "deny")
        self.assertIn("blocked for test", payload.get("agent_message", ""))

    def test_codex_allow_still_silent(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            hook_runtime.emit_decision("codex", hook_runtime.PolicyDecision.allow())

        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
