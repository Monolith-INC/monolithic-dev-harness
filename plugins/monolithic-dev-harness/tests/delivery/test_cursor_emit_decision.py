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

from host_adapters.hook_bridge import parse_policy_event, parse_tool_call
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

    def test_codex_deny_uses_pre_tool_contract(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            hook_runtime.emit_decision(
                "codex", hook_runtime.PolicyDecision.deny("blocked for test")
            )
        payload = json.loads(stdout.getvalue())["hookSpecificOutput"]
        self.assertEqual(payload["hookEventName"], "PreToolUse")
        self.assertEqual(payload["permissionDecision"], "deny")
        self.assertEqual(payload["permissionDecisionReason"], "blocked for test")


class TestHostAdapterBoundary(unittest.TestCase):
    def test_codex_patch_is_normalized_before_policy(self):
        payload = {
            "cwd": "/work/app",
            "tool_name": "apply_patch",
            "tool_input": {
                "command": "*** Begin Patch\n*** Update File: lib/a.dart\n*** Move to: lib/b.dart\n*** End Patch"
            },
        }
        call = parse_tool_call("codex", "pre-tool", payload)
        self.assertEqual(call.kind, "edit")
        self.assertEqual(
            call.file_paths, ("/work/app/lib/a.dart", "/work/app/lib/b.dart")
        )
        self.assertEqual(parse_policy_event("codex", payload, "/work/app").kind, "edit")

    def test_host_shell_dialects_share_one_contract(self):
        cases = (
            (
                "claude",
                "pre-tool",
                {"tool_name": "Bash", "tool_input": {"command": "git push"}},
            ),
            ("cursor", "shell", {"command": "git push"}),
            (
                "codex",
                "pre-tool",
                {"tool_name": "Bash", "tool_input": {"command": "git push"}},
            ),
        )
        for host, event, payload in cases:
            with self.subTest(host=host):
                call = parse_tool_call(host, event, payload)
                self.assertEqual(
                    (call.name, call.kind, call.command), ("shell", "shell", "git push")
                )

    def test_mcp_name_is_normalized_before_policy(self):
        call = parse_tool_call(
            "codex",
            "pre-tool",
            {
                "tool_name": "mcp__azure-devops__tracker_transition_work_item",
                "tool_input": {"state": "done"},
            },
        )
        self.assertEqual(
            (call.kind, call.server, call.name),
            ("mcp", "azure-devops", "tracker_transition_work_item"),
        )

    def test_shared_rules_do_not_parse_host_dialects(self):
        source = (ROOT / "scripts" / "harness" / "rules.py").read_text()
        self.assertFalse(
            any(
                dialect in source
                for dialect in ("apply_patch", "CommandLine", "AbsolutePath", "mcp__")
            )
        )


if __name__ == "__main__":
    unittest.main()
