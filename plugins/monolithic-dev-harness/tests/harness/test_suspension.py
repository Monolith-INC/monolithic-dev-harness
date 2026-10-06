"""Suspension: the user's typed `harness suspend` releases every check but `human-owned`."""

from __future__ import annotations

import json
import subprocess
import unittest

from harness import state
from tests.harness.test_hook_rules import AZ, PLUGIN_ROOT, HookTestCase
from tests.harness.test_questions import PLAIN, ask

HARNESS = PLUGIN_ROOT / "bin" / "harness"
WRITE = AZ + "wit_work_item_write"
CURSOR_WRITE = {"tool_name": "wit_work_item_write", "tool_input": "{}"}


class SuspensionTestCase(HookTestCase):
    def type(self, prompt: str, host: str = "claude") -> None:
        self.hook(host, "prompt", {"prompt": prompt})

    def mode(self) -> str:
        return state.harness_mode(self.repo)

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(HARNESS), "suspension", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def bash(self, command: str) -> dict | None:
        return self.claude("Bash", {"command": command})


class TestTypedSwitch(SuspensionTestCase):
    def test_typed_suspend_releases_the_rules_and_resume_restores_them(self) -> None:
        self.assertDenied(self.claude(WRITE, {"action": "create"}), "approval-required")
        self.type("harness suspend")
        self.assertEqual(self.mode(), "suspended")
        self.assertAllowed(self.claude(WRITE, {"action": "create"}))
        self.assertAllowed(self.bash("git push --force origin feature/1-demo"))
        self.type("Harness resume.")
        self.assertEqual(self.mode(), "active")
        self.assertDenied(self.claude(WRITE, {"action": "create"}), "approval-required")

    def test_every_host_records_the_typed_switch(self) -> None:
        for host in ("claude", "codex", "cursor"):
            with self.subTest(host=host):
                self.type("harness suspend", host)
                self.assertEqual(self.mode(), "suspended")
                self.type("harness resume", host)
                self.assertEqual(self.mode(), "active")

    def test_a_mention_inside_a_longer_message_does_not_switch(self) -> None:
        for prompt in (
            "don't run harness suspend yet",
            "what does harness suspend do?",
            "`harness suspend` and then push",
        ):
            with self.subTest(prompt=prompt):
                self.type(prompt)
                self.assertEqual(self.mode(), "active")

    def test_codex_and_cursor_are_released(self) -> None:
        self.assertDenied(self.codex(WRITE, {"action": "create"}), "approval-required")
        self.assertDenied(self.hook("cursor", "mcp", CURSOR_WRITE), "approval-required")
        self.type("harness suspend")
        self.assertAllowed(self.codex(WRITE, {"action": "create"}))
        self.assertAllowed(self.hook("cursor", "mcp", CURSOR_WRITE))

    def test_the_workflow_policy_is_released(self) -> None:
        tracking = self.repo / ".harness" / "state" / "tracking.json"
        tracking.write_text(json.dumps({"mode": "enforced"}))
        target = str(self.repo / "lib" / "main.dart")
        result = self.claude("Write", {"file_path": target})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.type("harness suspend")
        self.assertAllowed(self.claude("Write", {"file_path": target}))

    def test_human_owned_records_stay_protected_while_suspended(self) -> None:
        self.type("harness suspend")
        record = str(self.repo / ".harness/state/suspension.json")
        self.assertDenied(
            self.claude(
                "Edit", {"file_path": str(self.repo / ".harness/settings.json")}
            ),
            "human-owned",
        )
        self.assertDenied(self.claude("Write", {"file_path": record}), "human-owned")
        self.assertDenied(
            self.bash("echo '{}' > .harness/state/suspension.json"), "human-owned"
        )

    def test_a_suspended_repository_with_broken_settings_is_released(self) -> None:
        (self.repo / ".harness" / "settings.json").write_text("{not json")
        self.assertDenied(self.bash("touch notes.txt"), "harness-error")
        self.type("harness suspend")
        self.assertAllowed(self.bash("touch notes.txt"))

    def test_a_repository_without_settings_can_be_suspended(self) -> None:
        (self.repo / ".harness" / "settings.json").unlink()
        self.type("harness suspend")
        self.assertEqual(self.mode(), "suspended")
        self.assertAllowed(self.bash("echo x > .harness/state/suspension.json"))


class TestTheAgentCannotSuspend(SuspensionTestCase):
    def test_the_cli_offers_no_suspend(self) -> None:
        result = self.cli("suspend", "--repo", str(self.repo))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.mode(), "active")

    def test_no_command_text_slips_past_the_rules(self) -> None:
        (self.repo / ".harness" / "settings.json").write_text("{not json")
        for command in (
            f"{HARNESS} suspension status",
            f'{HARNESS} suspension status --repo "$(touch P1)/.."',
            f"{HARNESS} suspension status --repo x;touch${{IFS}}P2;/..",
            f"{HARNESS} policies suspend --repo x|touch${{IFS}}P3|/..",
        ):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "harness-error")

    def test_a_command_argument_on_another_tool_changes_nothing(self) -> None:
        smuggled = {"action": "create", "command": f"{HARNESS} suspension status"}
        self.assertDenied(self.claude(WRITE, smuggled), "approval-required")


class TestWhileSuspended(SuspensionTestCase):
    def test_questions_are_not_reworded_but_clicks_still_approve(self) -> None:
        wordy = {
            "questions": [
                {
                    "question": "Should I edit lib/main.dart and lib/other.dart, "
                    "and also rename `FooBarService` in the tracker?",
                    "header": "Edit",
                    "options": [
                        {"label": "Yes", "description": "go"},
                        {"label": "No", "description": "stop"},
                    ],
                    "multiSelect": False,
                }
            ]
        }
        payload = {"tool_name": "AskUserQuestion", "tool_input": wordy}
        self.assertDenied(self.hook("claude", "ask", payload), "plain-questions")
        self.type("harness suspend")
        self.assertAllowed(self.hook("claude", "ask", payload))

        self.hook("claude", "ask", {"tool_use_id": "toolu_1", "tool_input": ask()})
        answered = {**ask(), "answers": {PLAIN: "Approve"}}
        self.hook(
            "claude",
            "answer",
            {
                "tool_use_id": "toolu_1",
                "tool_input": answered,
                "tool_response": answered,
            },
        )
        self.assertIsNotNone(state.active_approval(self.repo))


class TestSuspensionCommand(SuspensionTestCase):
    def test_status_and_resume(self) -> None:
        status = self.cli("status", "--repo", str(self.repo))
        self.assertEqual(json.loads(status.stdout), {"mode": "active"})
        self.type("harness suspend")
        status = self.cli("status", "--repo", str(self.repo))
        self.assertEqual(json.loads(status.stdout), {"mode": "suspended"})
        resumed = self.cli("resume", "--repo", str(self.repo))
        self.assertEqual(json.loads(resumed.stdout), {"mode": "active"})
        self.assertEqual(self.mode(), "active")

    def test_a_missing_repository_is_refused_and_nothing_is_created(self) -> None:
        missing = self.repo.parent / "typo"
        result = self.cli("resume", "--repo", str(missing))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(missing.exists())

    def test_doctor_warns_while_suspended(self) -> None:
        self.type("harness suspend")
        doctor = subprocess.run(
            [str(HARNESS), "doctor", "--repo", str(self.repo)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertIn("harness checks — suspended", doctor.stdout)


if __name__ == "__main__":
    unittest.main()
