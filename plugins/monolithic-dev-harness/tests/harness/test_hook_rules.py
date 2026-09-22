"""End-to-end tests for the harness hook: every rule has a deny case and an allow case.

Each test drives `scripts/harness/hook.py` as a subprocess with a real host payload against a
throwaway git repository, the same way Claude Code and Cursor invoke it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOOK = PLUGIN_ROOT / "scripts" / "harness" / "hook.py"
CHECKS = PLUGIN_ROOT / "scripts" / "harness" / "checks.py"
VERDICT = PLUGIN_ROOT / "scripts" / "harness" / "review_verdict.py"
AZ = "mcp__plugin_monolithic-dev-harness_azure-devops__"

POLICY = {
    "schemaVersion": 1,
    "azure": {"project": "demo", "protected_work_items": [1001]},
    "git": {"base_branch": "develop"},
    "checks": [
        {"name": "unit", "run": "true", "when": ["lib/**"]},
        {"name": "rules", "run": "true", "when": ["security.rules"]},
    ],
    "tests_required": [
        {
            "source": ["lib/**/*.dart"],
            "tests": ["test/**/*_test.dart"],
            "exclude": ["**/*.g.dart"],
        }
    ],
    "generated": ["**/*.g.dart"],
    "guarded_paths": [
        {"path": "security.rules", "evidence": "check:rules"},
        {"path": "infra/main.tf", "evidence": "manual:infra"},
    ],
}
INTEGRATIONS = {
    "schemaVersion": 1,
    "branchTemplate": "{category}/{key}-{slug}",
    "scm": {"adapter": "github", "connection": {"command": "true", "args": []}},
    "tracker": {
        "adapter": "linear",
        "bindings": {},
        "connection": {"command": "true", "args": []},
    },
    "tracking": {"mode": "skipped"},
}


def sh(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


class HookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "app"
        self.repo.mkdir()
        sh(self.repo, "init", "-q", "-b", "develop")
        (self.repo / ".gitignore").write_text(".harness/state/\n")
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness" / "policy.json").write_text(json.dumps(POLICY))
        (self.repo / ".codex-workflows").mkdir()
        (self.repo / ".codex-workflows" / "integrations.json").write_text(
            json.dumps(INTEGRATIONS)
        )
        sh(self.repo, "add", "-A")
        sh(self.repo, "commit", "-q", "-m", "init")
        sh(self.repo, "checkout", "-q", "-b", "feature/1-demo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def hook(self, host: str, event: str, payload: dict) -> dict | None:
        payload = {"cwd": str(self.repo), **payload}
        proc = subprocess.run(
            [sys.executable, str(HOOK), "--host", host, "--event", event],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=self.repo,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout.strip()
        if not out:
            return None
        try:
            return json.loads(out.splitlines()[-1])
        except json.JSONDecodeError:
            return {"text": out}

    def claude(self, tool: str, tool_input: dict) -> dict | None:
        return self.hook(
            "claude", "pre-tool", {"tool_name": tool, "tool_input": tool_input}
        )

    def assertDenied(self, result: dict | None, rule: str) -> None:
        self.assertIsNotNone(result, "expected a deny decision")
        if "hookSpecificOutput" in result:
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn(
                f"[harness {rule}]",
                result["hookSpecificOutput"]["permissionDecisionReason"],
            )
        else:
            self.assertEqual(result.get("permission"), "deny")
            self.assertIn(f"[harness {rule}]", result["agent_message"])

    def assertAllowed(self, result: dict | None) -> None:
        if result is None:
            return
        if "hookSpecificOutput" in result:
            self.assertNotEqual(
                result["hookSpecificOutput"]["permissionDecision"], "deny", result
            )
        else:
            self.assertEqual(result.get("permission"), "allow", result)

    def approve(self, host: str = "claude") -> None:
        self.hook(host, "prompt", {"prompt": "Looks right. approve HB-TEST1"})

    def write(self, rel: str, content: str = "x\n") -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit_call(self) -> dict | None:
        return self.claude("Bash", {"command": "git commit -m 'work'"})


class TestOptIn(HookTestCase):
    def test_repo_without_policy_is_not_governed(self) -> None:
        (self.repo / ".harness" / "policy.json").unlink()
        self.assertAllowed(
            self.claude(AZ + "wit_work_item_write", {"action": "create"})
        )
        self.assertAllowed(
            self.hook(
                "cursor",
                "mcp",
                {"tool_name": "wit_work_item_write", "tool_input": "{}"},
            )
        )

    def test_read_calls_pass(self) -> None:
        self.assertAllowed(self.claude("Read", {"file_path": str(self.repo / "x")}))
        self.assertAllowed(
            self.claude(AZ + "wit_work_item", {"action": "get", "id": 1001})
        )


class TestHumanOwned(HookTestCase):
    def test_agent_cannot_write_approvals_or_policy(self) -> None:
        self.assertDenied(
            self.claude(
                "Write",
                {"file_path": str(self.repo / ".harness/state/approvals/HB-X.json")},
            ),
            "human-owned",
        )
        self.assertDenied(
            self.claude("Edit", {"file_path": str(self.repo / ".harness/policy.json")}),
            "human-owned",
        )
        self.assertDenied(
            self.claude(
                "Bash", {"command": "echo {} > .harness/state/manual/storage-abc.json"}
            ),
            "human-owned",
        )
        for command in (
            "cp /tmp/p.json .harness/policy.json",
            "sed -i 's/4007//' .harness/policy.json",
            "python3 -c \"open('.harness/policy.json', 'w').write('{}')\"",
            "echo '{}' | tee .harness/state/approvals/HB-1.json",
            "cd .harness/state/approvals && echo '{}' > HB-2.json",
            "ls 2>/dev/null; echo x >> .harness/policy.json",
        ):
            self.assertDenied(self.claude("Bash", {"command": command}), "human-owned")

    def test_other_state_and_files_are_writable(self) -> None:
        self.assertAllowed(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")})
        )
        self.assertAllowed(self.claude("Bash", {"command": "cat .harness/policy.json"}))
        for command in (
            "ls -la .harness/ && cat .harness/policy.json 2>/dev/null | head -80",
            "jq .azure .harness/policy.json > /tmp/azure.json",
            "cd .harness && ls state 2>/dev/null",
        ):
            self.assertAllowed(self.claude("Bash", {"command": command}))


class TestApproval(HookTestCase):
    def test_write_without_approval_is_denied_on_both_hosts(self) -> None:
        self.assertDenied(
            self.claude(AZ + "wit_work_item_write", {"action": "create"}),
            "approval-required",
        )
        self.assertDenied(
            self.hook(
                "cursor",
                "mcp",
                {
                    "tool_name": "wit_work_item_write",
                    "tool_input": '{"action":"create"}',
                },
            ),
            "approval-required",
        )
        self.assertDenied(
            self.claude(
                "mcp__plugin_monolithic-dev-harness_workflow-integrations__tracker_transition_work_item",
                {"ref": "12"},
            ),
            "approval-required",
        )
        self.assertDenied(
            self.claude(
                "mcp__plugin_monolithic-dev-harness_workflow-integrations__workflow_skip_tracker",
                {},
            ),
            "approval-required",
        )

    def test_user_approval_opens_the_window_and_logs_writes(self) -> None:
        self.approve()
        self.assertAllowed(
            self.claude(
                AZ + "wit_work_item_write", {"action": "create", "workItemType": "Epic"}
            )
        )
        records = list((self.repo / ".harness/state/approvals").glob("*.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(
            json.loads(records[0].read_text())["writes"][0]["tool"],
            "wit_work_item_write",
        )

    def test_git_push_needs_the_window_too(self) -> None:
        self.assertDenied(
            self.claude("Bash", {"command": "git push -u origin feature/1-demo"}),
            "approval-required",
        )
        self.assertDenied(
            self.hook("cursor", "shell", {"command": "git -C . push"}),
            "approval-required",
        )
        self.approve()
        self.assertAllowed(
            self.claude("Bash", {"command": "git push -u origin feature/1-demo"})
        )
        self.assertAllowed(self.claude("Bash", {"command": "git status && git log -1"}))

    def test_cursor_prompt_approval_and_revoke(self) -> None:
        self.assertEqual(
            self.hook("cursor", "prompt", {"prompt": "aprovo HB-CUR01"}),
            {"continue": True},
        )
        self.assertAllowed(
            self.hook(
                "cursor",
                "mcp",
                {"tool_name": "wit_work_item_link_write", "tool_input": "{}"},
            )
        )
        self.hook("claude", "prompt", {"prompt": "harness revoke"})
        self.assertDenied(
            self.hook(
                "cursor",
                "mcp",
                {"tool_name": "wit_work_item_link_write", "tool_input": "{}"},
            ),
            "approval-required",
        )


class TestProtected(HookTestCase):
    def test_protected_item_is_never_written_or_linked_even_with_approval(self) -> None:
        self.approve()
        self.assertDenied(
            self.claude(
                AZ + "wit_work_item_write",
                {"action": "update", "id": 1001, "updates": []},
            ),
            "protected-items",
        )
        self.assertDenied(
            self.claude(
                AZ + "wit_work_item_link_write",
                {
                    "action": "link",
                    "updates": [{"id": 9001, "linkToId": 1001, "type": "related"}],
                },
            ),
            "protected-items",
        )
        self.assertDenied(
            self.claude(
                AZ + "wit_work_item_write",
                {"action": "add_child", "parentId": 1001, "items": []},
            ),
            "protected-items",
        )

    def test_mentioning_a_protected_item_in_text_is_denied(self) -> None:
        self.approve()
        for text in (
            "Copia da Idea #1001",
            "Origem: https://dev.azure.com/org/demo/_workitems/edit/1001",
        ):
            self.assertDenied(
                self.claude(
                    AZ + "wit_work_item_write",
                    {
                        "action": "create",
                        "workItemType": "Feature",
                        "fields": [{"name": "System.Description", "value": text}],
                    },
                ),
                "protected-items",
            )

    def test_plain_text_names_and_html_entities_are_allowed(self) -> None:
        self.approve()
        self.assertAllowed(
            self.claude(
                AZ + "wit_work_item_write",
                {
                    "action": "create",
                    "workItemType": "Feature",
                    "fields": [
                        {
                            "name": "System.Description",
                            "value": "## &#1001; Origem\nCopia da Idea 1001, relacionada a #9001",
                        }
                    ],
                },
            )
        )

    def test_other_items_are_writable_with_approval(self) -> None:
        self.approve()
        self.assertAllowed(
            self.claude(
                AZ + "wit_work_item_write",
                {"action": "update", "id": 9001, "updates": []},
            )
        )


class TestTestsRequired(HookTestCase):
    def test_source_change_without_tests_is_denied(self) -> None:
        self.write("lib/a.dart")
        sh(self.repo, "add", "lib/a.dart")
        self.assertDenied(self.commit_call(), "tests-with-code")

    def test_source_change_with_tests_in_commit_or_branch_is_allowed(self) -> None:
        self.write("test/a_test.dart")
        sh(self.repo, "add", "test/a_test.dart")
        sh(self.repo, "commit", "-q", "-m", "test first")
        self.write("lib/a.dart")
        sh(self.repo, "add", "lib/a.dart")
        self.assertAllowed(self.commit_call())

    def test_generated_sources_are_excluded(self) -> None:
        self.write("lib/a.g.dart")
        sh(self.repo, "add", "lib/a.g.dart")
        self.assertAllowed(self.commit_call())


class TestGenerated(HookTestCase):
    def test_hand_edit_of_generated_file_is_denied(self) -> None:
        self.assertDenied(
            self.claude("Edit", {"file_path": str(self.repo / "lib/a.g.dart")}),
            "generated-files",
        )
        self.assertDenied(
            self.hook(
                "cursor",
                "pre-tool",
                {"tool_name": "StrReplace", "tool_input": {"path": "lib/x/b.g.dart"}},
            ),
            "generated-files",
        )
        self.assertDenied(
            self.claude("Bash", {"command": "sed -i 's/a/b/' lib/a.g.dart"}),
            "generated-files",
        )

    def test_regular_edit_and_generator_run_are_allowed(self) -> None:
        self.assertAllowed(
            self.claude("Edit", {"file_path": str(self.repo / "lib/a.dart")})
        )
        self.assertAllowed(
            self.claude("Bash", {"command": "dart run build_runner build"})
        )


class TestGuarded(HookTestCase):
    def test_guarded_path_needs_check_evidence_for_the_staged_tree(self) -> None:
        self.write("security.rules")
        sh(self.repo, "add", "security.rules")
        self.assertDenied(self.commit_call(), "guarded-paths")
        subprocess.run(
            [
                sys.executable,
                str(CHECKS),
                "--repo",
                str(self.repo),
                "--staged",
                "--only",
                "rules",
            ],
            check=True,
            capture_output=True,
        )
        self.assertAllowed(self.commit_call())
        self.write("security.rules", "changed after the check\n")
        sh(self.repo, "add", "security.rules")
        self.assertDenied(self.commit_call(), "guarded-paths")

    def test_manual_guard_needs_the_users_record(self) -> None:
        self.write("infra/main.tf")
        sh(self.repo, "add", "infra/main.tf")
        self.assertDenied(self.commit_call(), "guarded-paths")
        self.hook(
            "claude",
            "prompt",
            {"prompt": "validated by hand: harness manual-check infra ok"},
        )
        self.assertAllowed(self.commit_call())


class TestPullRequest(HookTestCase):
    def pr(self, **extra: object) -> dict | None:
        return self.claude(
            AZ + "repo_pull_request_write",
            {"action": "create", "repositoryId": "r", **extra},
        )

    def ship_ready_commit(self) -> None:
        self.write("test/a_test.dart")
        self.write("lib/a.dart")
        sh(self.repo, "add", "-A")
        sh(self.repo, "commit", "-q", "-m", "feature")

    def test_pr_must_be_draft_reviewed_and_checked(self) -> None:
        self.approve()
        self.ship_ready_commit()
        self.assertDenied(self.pr(isDraft=False), "draft-reviewed-prs")
        self.assertDenied(
            self.pr(isDraft=True), "draft-reviewed-prs"
        )  # no review verdict yet
        subprocess.run(
            [
                sys.executable,
                str(VERDICT),
                "--repo",
                str(self.repo),
                "--verdict",
                "ready",
                "--summary",
                "ok",
            ],
            check=True,
            capture_output=True,
        )
        self.assertDenied(
            self.pr(isDraft=True), "draft-reviewed-prs"
        )  # no check evidence yet
        subprocess.run(
            [sys.executable, str(CHECKS), "--repo", str(self.repo)],
            check=True,
            capture_output=True,
        )
        self.assertAllowed(self.pr(isDraft=True))

    def test_new_commit_invalidates_the_verdict(self) -> None:
        self.approve()
        self.ship_ready_commit()
        subprocess.run(
            [
                sys.executable,
                str(VERDICT),
                "--repo",
                str(self.repo),
                "--verdict",
                "ready",
                "--summary",
                "ok",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [sys.executable, str(CHECKS), "--repo", str(self.repo)],
            check=True,
            capture_output=True,
        )
        self.write("lib/b.dart")
        sh(self.repo, "add", "-A")
        sh(self.repo, "commit", "-q", "-m", "more")
        self.assertDenied(self.pr(isDraft=True), "draft-reviewed-prs")

    def test_publishing_and_voting_are_human_only(self) -> None:
        self.approve()
        self.assertDenied(
            self.claude(
                AZ + "repo_pull_request_write",
                {"action": "update", "pullRequestId": 1, "isDraft": False},
            ),
            "draft-reviewed-prs",
        )
        self.assertDenied(
            self.claude(
                AZ + "repo_pull_request_write",
                {"action": "vote", "pullRequestId": 1, "vote": "Approved"},
            ),
            "draft-reviewed-prs",
        )


class TestPolicyValidation(HookTestCase):
    def test_guarded_path_naming_an_unknown_check_fails_closed(self) -> None:
        policy = json.loads((self.repo / ".harness" / "policy.json").read_text())
        policy["guarded_paths"].append(
            {"path": "db/**", "evidence": "check:does-not-exist"}
        )
        (self.repo / ".harness" / "policy.json").write_text(json.dumps(policy))
        self.assertDenied(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")}),
            "harness-error",
        )
        self.assertAllowed(
            self.claude("Read", {"file_path": str(self.repo / "lib/a.dart")})
        )


class TestFailClosed(HookTestCase):
    def test_broken_policy_blocks_writes_but_not_reads(self) -> None:
        (self.repo / ".harness" / "policy.json").write_text("{not json")
        self.assertDenied(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")}),
            "harness-error",
        )
        self.assertAllowed(
            self.claude("Read", {"file_path": str(self.repo / "lib/a.dart")})
        )


if __name__ == "__main__":
    unittest.main()
