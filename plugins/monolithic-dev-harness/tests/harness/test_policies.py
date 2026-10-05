"""`harness policies suspend|resume|status`: the human's switch for every harness check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from tests.harness.test_hook_rules import AZ, PLUGIN_ROOT, HookTestCase

HARNESS = PLUGIN_ROOT / "bin" / "harness"
WRITE = AZ + "wit_work_item_write"


class PoliciesTestCase(HookTestCase):
    def policies(self, operation: str) -> dict:
        proc = subprocess.run(
            [str(HARNESS), "policies", operation, "--repo", str(self.repo)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def bash(self, command: str) -> dict | None:
        return self.claude("Bash", {"command": command})

    def assertDeniedAny(self, result: dict | None) -> None:
        self.assertIsNotNone(result, "expected a deny decision")
        output = result.get("hookSpecificOutput", result)
        self.assertEqual(
            output.get("permissionDecision", output.get("permission")), "deny", result
        )


class TestSuspension(PoliciesTestCase):
    def test_status_starts_active(self) -> None:
        self.assertEqual(self.policies("status"), {"mode": "active"})

    def test_suspend_releases_the_rules_and_resume_restores_them(self) -> None:
        self.assertDenied(self.claude(WRITE, {"action": "create"}), "approval-required")
        self.assertEqual(self.policies("suspend"), {"mode": "suspended"})
        self.assertEqual(self.policies("status"), {"mode": "suspended"})
        self.assertAllowed(self.claude(WRITE, {"action": "create"}))
        self.assertAllowed(self.bash("git push --force origin feature/1-demo"))
        self.assertEqual(self.policies("resume"), {"mode": "active"})
        self.assertDenied(self.claude(WRITE, {"action": "create"}), "approval-required")

    def test_human_owned_records_stay_protected_while_suspended(self) -> None:
        self.policies("suspend")
        self.assertDenied(
            self.claude(
                "Edit", {"file_path": str(self.repo / ".harness/settings.json")}
            ),
            "human-owned",
        )
        self.assertDenied(
            self.bash("echo '{}' > .harness/state/policies.json"), "human-owned"
        )
        self.assertDenied(
            self.claude(
                "Write",
                {"file_path": str(self.repo / ".harness/state/policies.json")},
            ),
            "human-owned",
        )

    def test_codex_and_cursor_are_released_too(self) -> None:
        self.policies("suspend")
        self.assertAllowed(self.codex(WRITE, {"action": "create"}))
        self.assertAllowed(
            self.hook(
                "cursor",
                "mcp",
                {"tool_name": "wit_work_item_write", "tool_input": "{}"},
            )
        )

    def test_the_workflow_policy_is_released(self) -> None:
        tracking = self.repo / ".harness" / "state" / "tracking.json"
        tracking.write_text(json.dumps({"mode": "enforced"}))
        target = str(self.repo / "lib" / "main.dart")
        self.assertDeniedAny(self.claude("Write", {"file_path": target}))
        self.policies("suspend")
        self.assertAllowed(self.claude("Write", {"file_path": target}))

    def test_questions_are_not_rewritten_while_suspended(self) -> None:
        question = {
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
        payload = {"tool_name": "AskUserQuestion", "tool_input": question}
        self.assertDenied(self.hook("claude", "ask", payload), "plain-questions")
        self.policies("suspend")
        self.assertAllowed(self.hook("claude", "ask", payload))


class TestReleasingABrokenRepository(PoliciesTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.repo / ".harness" / "settings.json").write_text("{not json")

    def test_broken_settings_block_writes_but_not_the_suspend_command(self) -> None:
        self.assertDenied(self.bash("touch notes.txt"), "harness-error")
        for command in (
            f"{HARNESS} policies suspend",
            f"{HARNESS} policies status --repo .",
            f"{HARNESS} policies suspend --repo {self.repo}",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.bash(command))
        self.policies("suspend")
        self.assertAllowed(self.bash("touch notes.txt"))

    def test_only_the_exact_command_from_this_plugin_is_let_through(self) -> None:
        fake = self.repo / "bin" / "harness"
        fake.parent.mkdir()
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o755)
        for command in (
            "./bin/harness policies suspend",
            f"{HARNESS} policies suspend && touch notes.txt",
            f"{HARNESS} policies suspend --repo /elsewhere",
            f"{HARNESS} session start 1",
        ):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "harness-error")

    def test_the_installed_shell_command_is_trusted(self) -> None:
        # The installer links `harness` to the marketplace copy, which can differ from the copy
        # the host runs hooks from.
        installed = self.repo.parent / "marketplace" / "monolithic-dev-harness"
        (installed / "bin").mkdir(parents=True)
        (installed / "scripts" / "harness").mkdir(parents=True)
        (installed / "bin" / "harness").write_text(HARNESS.read_text())
        (installed / "bin" / "harness").chmod(0o755)
        (installed / "scripts" / "harness" / "policies.py").write_text("")
        link_dir = self.repo.parent / "path-bin"
        link_dir.mkdir()
        (link_dir / "harness").symlink_to(installed / "bin" / "harness")
        payload = {
            "cwd": str(self.repo),
            "tool_name": "Bash",
            "tool_input": {"command": "harness policies suspend"},
        }
        proc = subprocess.run(
            [
                sys.executable,
                str(PLUGIN_ROOT / "scripts/harness/hook.py"),
                *("--host", "claude", "--event", "pre-tool"),
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=self.repo,
            env={**os.environ, "PATH": f"{link_dir}{os.pathsep}{os.environ['PATH']}"},
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertAllowed(json.loads(proc.stdout) if proc.stdout.strip() else None)


if __name__ == "__main__":
    unittest.main()
