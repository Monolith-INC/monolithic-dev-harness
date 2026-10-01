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

from harness import sessions
from tests.settings_fixture import MINIMAL

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOOK = PLUGIN_ROOT / "scripts" / "harness" / "hook.py"
CHECKS = PLUGIN_ROOT / "scripts" / "harness" / "checks.py"
VERDICT = PLUGIN_ROOT / "scripts" / "harness" / "review_verdict.py"
AZ = "mcp__plugin_monolithic-dev-harness_azure-devops__"

SETTINGS = {
    **MINIMAL,
    "tracker": {
        "name": "azure-devops",
        "values": {"organization": "o", "project": "demo"},
    },
    "scm": {
        "name": "azure-repos",
        "values": {"organization": "o", "project": "demo", "repository": "app"},
    },
    "branch_template": "{category}/{key}-{slug}",
    "protected_work_items": ["1001"],
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
        (self.repo / ".harness" / "settings.json").write_text(json.dumps(SETTINGS))
        # The workflow runtime is covered by its own tests; these exercise the harness rules.
        (self.repo / ".harness" / "state").mkdir()
        (self.repo / ".harness" / "state" / "tracking.json").write_text(
            json.dumps({"mode": "skipped"})
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

    def codex(self, tool: str, tool_input: dict) -> dict | None:
        return self.hook(
            "codex", "pre-tool", {"tool_name": tool, "tool_input": tool_input}
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
    def test_repo_without_settings_is_not_governed(self) -> None:
        (self.repo / ".harness" / "settings.json").unlink()
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


class TestCodexAdapter(HookTestCase):
    def test_patch_targets_are_checked_before_editing(self) -> None:
        self.assertDenied(
            self.codex(
                "apply_patch",
                {
                    "command": "*** Begin Patch\n*** Update File: .harness/settings.json\n@@\n-old\n+new\n*** End Patch"
                },
            ),
            "human-owned",
        )
        self.assertAllowed(
            self.codex(
                "apply_patch",
                {
                    "command": "*** Begin Patch\n*** Update File: lib/a.dart\n@@\n-old\n+new\n*** End Patch"
                },
            )
        )
        self.assertDenied(
            self.codex(
                "apply_patch",
                {
                    "command": "*** Begin Patch\n*** Add File: lib/a.g.dart\n+generated\n*** End Patch"
                },
            ),
            "generated-files",
        )

    def test_patch_headers_are_read_the_way_codex_applies_them(self) -> None:
        for header in (
            "  *** Update File: .harness/settings.json",
            "*** Update File: .harness/settings.json\r",
            "*** Update File: .harness/settings.json ",
        ):
            with self.subTest(header=header):
                self.assertDenied(
                    self.codex(
                        "apply_patch",
                        {
                            "command": f"*** Begin Patch\n{header}\n@@\n-old\n+new\n*** End Patch"
                        },
                    ),
                    "human-owned",
                )
        self.assertDenied(
            self.codex(
                "apply_patch",
                {
                    "command": "*** Begin Patch\n*** Add File: lib/a.g.dart \n+generated\n*** End Patch"
                },
            ),
            "generated-files",
        )

    def test_patch_without_readable_targets_is_denied(self) -> None:
        self.assertDenied(
            self.codex(
                "apply_patch",
                {"command": "*** Begin Patch\n@@\n-old\n+new\n*** End Patch"},
            ),
            "human-owned",
        )

    def test_patch_paths_resolve_from_codex_working_directory(self) -> None:
        self.assertDenied(
            self.hook(
                "codex",
                "pre-tool",
                {
                    "cwd": str(self.repo / "lib"),
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: ../.harness/settings.json\n@@\n-old\n+new\n*** End Patch"
                    },
                },
            ),
            "human-owned",
        )

    def test_codex_prompt_records_approval_for_remote_write(self) -> None:
        self.assertDenied(
            self.codex(AZ + "wit_work_item_write", {"action": "create"}),
            "approval-required",
        )
        self.hook("codex", "prompt", {"prompt": "approve HB-TEST1"})
        self.assertAllowed(self.codex(AZ + "wit_work_item_write", {"action": "create"}))


class TestHumanOwned(HookTestCase):
    def test_agent_cannot_write_approvals_settings_or_sessions(self) -> None:
        self.assertDenied(
            self.claude(
                "Write",
                {"file_path": str(self.repo / ".harness/state/approvals/HB-X.json")},
            ),
            "human-owned",
        )
        self.assertDenied(
            self.claude(
                "Edit", {"file_path": str(self.repo / ".harness/settings.json")}
            ),
            "human-owned",
        )
        self.assertDenied(
            self.claude(
                "Bash", {"command": "echo {} > .harness/state/manual/storage-abc.json"}
            ),
            "human-owned",
        )
        for path in (
            ".harness/state/sessions/HS-1/events/0002-closed.json",
            ".harness/state/trackers/x.json",
            ".harness/state/tracking.json",
            ".harness/state/adoptions/HA-0123456789/approval.json",
        ):
            with self.subTest(path=path):
                self.assertDenied(
                    self.claude("Write", {"file_path": str(self.repo / path)}),
                    "human-owned",
                )
        for command in (
            "cp /tmp/p.json .harness/settings.json",
            "sed -i 's/4007//' .harness/settings.json",
            "python3 -c \"open('.harness/settings.json', 'w').write('{}')\"",
            "echo '{}' | tee .harness/state/approvals/HB-1.json",
            "cd .harness/state/approvals && echo '{}' > HB-2.json",
            "ls 2>/dev/null; echo x >> .harness/settings.json",
            # A second line is a second command, not more arguments to the first.
            "echo hi\ncp /tmp/p.json .harness/settings.json",
            "cd .harness\necho '{}' > settings.json",
            # Wrappers, dispatchers, and compound commands run the writer all the same.
            "env X=1 cp /tmp/p.json .harness/settings.json",
            "sudo tee .harness/settings.json",
            "echo .harness/settings.json | xargs rm",
            "eval 'cp /tmp/p .harness/settings.json'",
            "for f in a; do cp $f .harness/settings.json; done",
            "if true; then cp /tmp/p .harness/settings.json; fi",
            "(cd .harness && rm settings.json)",
            "P=.harness/settings.json; echo x > $P",
            # A directory target lands on the policy just as well as naming it.
            "cp /tmp/policy.json .harness/",
            "rsync -a /tmp/h/ .harness/",
            "tar -xf p.tar -C .harness",
            "unzip -o p.zip -d .harness",
            "ln -s .harness /tmp/h",
            "find .harness -name settings.json -delete",
        ):
            with self.subTest(command=command):
                self.assertDenied(
                    self.claude("Bash", {"command": command}), "human-owned"
                )

    def test_other_state_and_files_are_writable(self) -> None:
        self.assertAllowed(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")})
        )
        self.assertAllowed(
            self.claude("Bash", {"command": "cat .harness/settings.json"})
        )
        # Reading them is always fine, whatever else is on the line.
        for command in (
            "ls -la .harness/ && cat .harness/settings.json 2>/dev/null | head -80",
            "cd .harness && cat settings.json 2>&1 | head",
            "cd .harness && ls -la > /tmp/listing",
            "jq .azure .harness/settings.json > /tmp/azure.json",
            "shasum .harness/settings.json",
            "shellcheck .harness/settings.json",
            "git diff .harness/settings.json",
            "python3 -m json.tool .harness/state/approvals/HB-7Q2K.json",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.claude("Bash", {"command": command}))


class TestTrackers(HookTestCase):
    """Tracker writes and protections come from the tracker folders, whichever tracker is selected."""

    def select(self, tracker: dict, **changes) -> None:
        settings = {
            **json.loads((self.repo / ".harness" / "settings.json").read_text()),
            "tracker": tracker,
            **changes,
        }
        (self.repo / ".harness" / "settings.json").write_text(json.dumps(settings))

    def approve(self) -> None:
        self.hook("claude", "prompt", {"prompt": "approve HB-TRK1"})

    def test_a_write_any_tracker_declares_needs_approval(self) -> None:
        self.select({"name": "linear", "values": {"team": "ENG"}})
        self.assertDenied(
            self.claude("mcp__linear__save_issue", {"title": "x"}), "approval-required"
        )
        # The Azure DevOps server stays registered with the host whatever the repository selects.
        self.assertDenied(
            self.claude(AZ + "wit_work_item_write", {"action": "create"}),
            "approval-required",
        )
        self.assertAllowed(self.claude("mcp__linear__get_issue", {"id": "ENG-1"}))

    def test_a_protected_linear_issue_is_never_written_or_mentioned(self) -> None:
        self.select(
            {"name": "linear", "values": {"team": "ENG"}},
            protected_work_items=["ENG-12"],
        )
        self.approve()
        self.assertDenied(
            self.claude("mcp__linear__save_issue", {"id": "eng-12", "title": "x"}),
            "protected-items",
        )
        self.assertDenied(
            self.claude(
                "mcp__linear__save_comment",
                {"issueId": "ENG-3", "body": "follows up ENG-12"},
            ),
            "protected-items",
        )
        self.assertDenied(
            self.claude("Bash", {"command": "git commit -m 'fix ENG-12'"}),
            "protected-items",
        )
        self.assertAllowed(
            self.claude(
                "mcp__linear__save_comment", {"issueId": "ENG-3", "body": "see ENG-120"}
            )
        )

    def test_local_tracker_mentions_do_not_link(self) -> None:
        self.select({"name": "local"}, protected_work_items=["STORY-0001"])
        self.assertAllowed(
            self.claude(
                "Bash", {"command": "git commit --allow-empty -m 'STORY-0001 notes'"}
            )
        )

    def test_a_broken_selected_tracker_refuses_tracker_writes(self) -> None:
        self.select({"name": "azure-devops", "values": {"organization": "o"}})
        self.approve()
        self.assertDenied(
            self.claude(AZ + "wit_work_item_write", {"action": "create"}),
            "tracker-invalid",
        )
        self.select({"name": "nothing"})
        self.assertDenied(
            self.claude(
                "mcp__plugin_x_workflow-integrations__tracker_create_work_item", {}
            ),
            "tracker-invalid",
        )
        self.assertAllowed(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")})
        )

    def test_an_untrusted_selected_tracker_fails_closed_for_its_own_writes(
        self,
    ) -> None:
        import shutil

        folder = self.repo / ".harness" / "trackers" / "custom"
        shutil.copytree(PLUGIN_ROOT / "trackers" / "local", folder)
        manifest = json.loads((folder / "tracker.json").read_text())
        writes = {"server": "customsrv", "tools": ["save_*"]}
        (folder / "tracker.json").write_text(
            json.dumps({**manifest, "name": "custom", "writes": writes})
        )
        self.select({"name": "custom", "source": "onboarded"})
        self.approve()
        # Untrusted, its manifest cannot say which tools write: every call to its server counts.
        self.assertDenied(
            self.claude("mcp__customsrv__save_thing", {}), "tracker-invalid"
        )
        self.assertDenied(
            self.claude("mcp__customsrv__anything", {}), "tracker-invalid"
        )
        self.assertAllowed(
            self.claude(
                "mcp__plugin_x_workflow-integrations__workflow_tracking_status", {}
            )
        )

    def test_a_broken_onboarded_tracker_that_is_not_selected_still_needs_approval(
        self,
    ) -> None:
        """A folder that fails its checks (here, a manifest with little but its writes) may not
        quietly drop its server's writes from the approval rule."""
        folder = self.repo / ".harness" / "trackers" / "custom"
        folder.mkdir(parents=True)
        (folder / "tracker.json").write_text(
            json.dumps(
                {
                    "name": "custom",
                    "writes": {"server": "customsrv", "tools": ["save_*"]},
                }
            )
        )
        self.assertDenied(
            self.claude("mcp__customsrv__save_thing", {}), "approval-required"
        )
        self.assertAllowed(self.claude("mcp__customsrv__get_thing", {}))

    def test_an_onboarded_folder_that_does_not_say_what_writes_fails_closed(
        self,
    ) -> None:
        folder = self.repo / ".harness" / "trackers" / "custom"
        folder.mkdir(parents=True)
        (folder / "tracker.json").write_text("{ not json")
        self.approve()
        self.assertDenied(
            self.claude("mcp__customsrv__anything", {}), "tracker-invalid"
        )

    def test_linking_a_protected_item_through_the_gateway_is_denied(self) -> None:
        self.approve()
        call = "mcp__plugin_x_workflow-integrations__scm_link_work_item"
        self.assertDenied(
            self.claude(call, {"pullRequestRef": "12", "workItemRef": "1001"}),
            "protected-items",
        )
        self.assertAllowed(
            self.claude(call, {"pullRequestRef": "12", "workItemRef": "1002"})
        )


class TestTrackerTrustByClick(HookTestCase):
    """The user trusts, selects, and stops trusting an onboarded tracker with a click."""

    TRUST = "Trust the Acme Boards tracker as I just described it?"
    USE = "Use Acme Boards as this project's tracker now?"
    STOP = "Stop trusting the Acme Boards tracker?"

    def setUp(self) -> None:
        super().setUp()
        import shutil

        self.folder = self.repo / ".harness" / "trackers" / "acme"
        shutil.copytree(
            PLUGIN_ROOT / "trackers" / "local",
            self.folder,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        manifest = json.loads((self.folder / "tracker.json").read_text())
        (self.folder / "tracker.json").write_text(
            json.dumps({**manifest, "name": "acme", "label": "Acme Boards"})
        )
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

    def question(self, text: str, labels: tuple[str, str]) -> dict:
        return {
            "questions": [
                {
                    "question": text,
                    "header": "Tracker",
                    "multiSelect": False,
                    "options": [
                        {"label": label, "description": "What this choice does."}
                        for label in labels
                    ],
                }
            ]
        }

    def ask(self, text: str, labels: tuple[str, str], use_id: str) -> dict | None:
        return self.hook(
            "claude",
            "ask",
            {
                "tool_name": "AskUserQuestion",
                "tool_use_id": use_id,
                "tool_input": self.question(text, labels),
            },
        )

    def click(
        self, text: str, labels: tuple[str, str], choice: str, use_id: str
    ) -> str:
        answered = {**self.question(text, labels), "answers": {text: choice}}
        result = self.hook(
            "claude",
            "answer",
            {
                "tool_name": "AskUserQuestion",
                "tool_use_id": use_id,
                "tool_input": self.question(text, labels),
                "tool_response": answered,
            },
        )
        return (result or {}).get("hookSpecificOutput", {}).get("additionalContext", "")

    def trusted(self) -> bool:
        from integrations import trust

        return trust.is_trusted(self.repo, "acme", self.folder)

    def settings(self) -> dict:
        return json.loads((self.repo / ".harness" / "settings.json").read_text())

    def trust_by_click(self) -> str:
        labels = ("Trust", "Not now")
        self.assertIsNone(self.ask(self.TRUST, labels, "toolu_trust"))
        return self.click(self.TRUST, labels, "Trust", "toolu_trust")

    def test_clicking_trust_trusts_the_version_the_question_was_about(self) -> None:
        note = self.trust_by_click()
        self.assertIn("trusts the Acme Boards tracker", note)
        self.assertTrue(self.trusted())

    def test_a_trust_click_opens_no_approval_window(self) -> None:
        from harness import state

        self.trust_by_click()
        self.assertIsNone(state.active_approval(self.repo))

    def test_an_edit_between_question_and_click_trusts_nothing(self) -> None:
        labels = ("Trust", "Not now")
        self.ask(self.TRUST, labels, "toolu_trust")
        (self.folder / "adapter.py").write_text("# changed after the question\n")
        note = self.click(self.TRUST, labels, "Trust", "toolu_trust")
        self.assertIn("changed", note)
        self.assertFalse(self.trusted())

    def test_not_now_trusts_nothing(self) -> None:
        labels = ("Trust", "Not now")
        self.ask(self.TRUST, labels, "toolu_trust")
        self.click(self.TRUST, labels, "Not now", "toolu_trust")
        self.assertFalse(self.trusted())

    def test_a_trust_question_must_name_a_staged_tracker(self) -> None:
        result = self.ask(
            "Trust the new tracker as I described it?", ("Trust", "Not now"), "toolu_x"
        )
        self.assertDenied(result, "plain-questions")
        self.assertIn("name the tracker", json.dumps(result))

    def test_an_unchecked_question_trusts_nothing(self) -> None:
        # The answer hook only acts on a question the ask hook let through.
        self.click(self.TRUST, ("Trust", "Not now"), "Trust", "toolu_never_asked")
        self.assertFalse(self.trusted())

    def test_clicking_use_it_selects_the_trusted_tracker_in_the_settings(self) -> None:
        (self.folder / "values.json").write_text(json.dumps({}))
        self.trust_by_click()
        before = self.settings()
        labels = ("Use it", "Keep the current one")
        self.assertIsNone(self.ask(self.USE, labels, "toolu_use"))
        note = self.click(self.USE, labels, "Use it", "toolu_use")
        self.assertIn("now uses the Acme Boards tracker", note)
        after = self.settings()
        self.assertEqual(
            after["tracker"], {"name": "acme", "source": "onboarded", "values": {}}
        )
        self.assertEqual(
            {k: v for k, v in after.items() if k != "tracker"},
            {k: v for k, v in before.items() if k != "tracker"},
        )

    def test_keep_the_current_one_changes_nothing(self) -> None:
        self.trust_by_click()
        before = self.settings()
        labels = ("Use it", "Keep the current one")
        self.ask(self.USE, labels, "toolu_use")
        self.click(self.USE, labels, "Keep the current one", "toolu_use")
        self.assertEqual(self.settings(), before)

    def test_an_untrusted_tracker_cannot_be_selected(self) -> None:
        before = self.settings()
        labels = ("Use it", "Keep the current one")
        self.ask(self.USE, labels, "toolu_use")
        note = self.click(self.USE, labels, "Use it", "toolu_use")
        self.assertIn("not trusted", note)
        self.assertEqual(self.settings(), before)

    def test_clicking_stop_trusting_withdraws_trust(self) -> None:
        self.trust_by_click()
        labels = ("Stop trusting", "Keep it")
        self.ask(self.STOP, labels, "toolu_stop")
        self.click(self.STOP, labels, "Stop trusting", "toolu_stop")
        self.assertFalse(self.trusted())

    def test_the_old_typed_line_does_nothing(self) -> None:
        from integrations import trust

        digest = trust.digest(self.folder)
        self.hook(
            "claude", "prompt", {"prompt": f"harness trust-tracker acme {digest[:12]}"}
        )
        self.assertFalse(self.trusted())

    def test_an_ordinary_question_with_a_use_it_option_is_not_a_tracker_question(
        self,
    ) -> None:
        before = self.settings()
        text, labels = "Should I reuse the cached build?", ("Use it", "Rebuild")
        self.assertIsNone(self.ask(text, labels, "toolu_cache"))
        self.click(text, labels, "Use it", "toolu_cache")
        self.assertEqual(self.settings(), before)

    def test_a_question_about_a_shipped_tracker_is_not_blocked(self) -> None:
        text, labels = "Use Linear as the tracker?", ("Use it", "Keep the current one")
        self.assertIsNone(self.ask(text, labels, "toolu_linear"))

    def test_the_longest_matching_label_wins(self) -> None:
        import shutil

        other = self.repo / ".harness" / "trackers" / "acme-lite"
        shutil.copytree(self.folder, other)
        manifest = json.loads((other / "tracker.json").read_text())
        (other / "tracker.json").write_text(
            json.dumps({**manifest, "name": "acme-lite", "label": "Acme"})
        )
        self.trust_by_click()
        self.assertTrue(self.trusted())
        from integrations import trust

        self.assertFalse(trust.is_trusted(self.repo, "acme-lite", other))

    def test_one_question_can_offer_trust_and_stop_trusting(self) -> None:
        self.trust_by_click()
        text = "What should happen to the Acme Boards tracker?"
        labels = ("Trust", "Stop trusting")
        self.ask(text, labels, "toolu_both")
        self.click(text, labels, "Stop trusting", "toolu_both")
        self.assertFalse(self.trusted())

    def test_stop_trusting_works_after_the_folder_is_gone(self) -> None:
        import shutil

        from integrations import trust

        self.trust_by_click()
        shutil.rmtree(self.folder)
        labels = ("Stop trusting", "Keep it")
        self.assertIsNone(self.ask(self.STOP, labels, "toolu_stop"))
        self.click(self.STOP, labels, "Stop trusting", "toolu_stop")
        self.assertEqual(trust.trusted_digest(self.repo, "acme"), "")

    def test_a_cursor_reply_counts_only_as_the_whole_message(self) -> None:
        from integrations import onboarding

        summary = onboarding.show(self.repo, "acme").value
        short = next(word for word in summary.split() if word.startswith("HT-"))
        self.hook("cursor", "prompt", {"prompt": f"what does approve {short} do?"})
        self.assertFalse(self.trusted())
        self.hook("cursor", "prompt", {"prompt": f"don't approve {short} yet"})
        self.assertFalse(self.trusted())

    def test_cursor_users_stop_trusting_by_name(self) -> None:
        from integrations import onboarding

        summary = onboarding.show(self.repo, "acme").value
        short = next(word for word in summary.split() if word.startswith("HT-"))
        self.hook("cursor", "prompt", {"prompt": f"approve {short}"})
        self.assertTrue(self.trusted())
        self.hook(
            "cursor", "prompt", {"prompt": "stop trusting the Acme Boards tracker"}
        )
        self.assertFalse(self.trusted())

    def test_cursor_users_reply_with_the_short_id_the_tracker_summary_shows(
        self,
    ) -> None:
        from integrations import onboarding

        summary = onboarding.show(self.repo, "acme").value
        short = next(word for word in summary.split() if word.startswith("HT-")).rstrip(
            "."
        )
        self.hook("cursor", "prompt", {"prompt": f"approve {short}"})
        self.assertTrue(self.trusted())
        self.hook("cursor", "prompt", {"prompt": f"use {short}"})
        self.assertEqual(self.settings()["tracker"]["name"], "acme")


class TestApproval(HookTestCase):
    def test_every_form_of_git_push_needs_approval(self) -> None:
        for command in (
            "git push",
            "sudo git push",
            "env X=1 git push",
            "(git push)",
            "if true; then git push; fi",
            "bash -c 'git push origin HEAD'",
        ):
            with self.subTest(command=command):
                self.assertDenied(
                    self.claude("Bash", {"command": command}), "approval-required"
                )

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

    def test_every_linking_form_of_a_protected_id_is_denied(self) -> None:
        self.approve()
        for text in (
            "Copia da Idea #1001",
            "AB#1001 origem",
            "US#1001",
            "Origem: https://dev.azure.com/org/demo/_workitems/edit/1001",
            "Origem: https://dev.azure.com/org/demo/_workitems/?_a=edit&id=1001",
            "vstfs:///WorkItemTracking/WorkItem/1001",
        ):
            with self.subTest(text=text):
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

    def test_commit_messages_link_through_any_mention_form(self) -> None:
        self.approve()
        # With Azure Repos' commit mention linking on, `#<id>` links as well as `AB#<id>`.
        for command in (
            "git commit -m 'closes #1001' && git push",
            "git commit -m 'Refs #1001'",
            "git commit -m 'AB#1001 done' && git push",
        ):
            with self.subTest(command=command):
                self.assertDenied(
                    self.claude("Bash", {"command": command}), "protected-items"
                )
        # Other items, and ids in plain text, are fine.
        for command in (
            "git commit -m 'closes #9001'",
            "git commit -m 'copy of Idea 1001'",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.claude("Bash", {"command": command}))

    def test_a_commit_mentioning_a_protected_item_is_denied_before_any_push(
        self,
    ) -> None:
        # The harness commits and pushes in separate calls; the push carries no text to check.
        self.assertDenied(
            self.claude("Bash", {"command": "git commit -m 'AB#1001 done'"}),
            "protected-items",
        )
        self.assertDenied(
            self.claude("Bash", {"command": "sudo git commit -m 'AB#1001 done'"}),
            "protected-items",
        )

    def test_setting_the_parent_field_is_linking(self) -> None:
        self.approve()
        for tool, payload in (
            (
                AZ + "wit_work_item_write",
                {
                    "action": "create",
                    "workItemType": "User Story",
                    "fields": [{"name": "System.Parent", "value": "1001"}],
                },
            ),
            (
                AZ + "wit_work_item_write",
                {
                    "action": "update",
                    "id": 9001,
                    "updates": [{"path": "/fields/System.Parent", "value": "1001"}],
                },
            ),
            (
                "mcp__plugin_monolithic-dev-harness_workflow-integrations__"
                "tracker_create_work_item",
                {"kind": "user_story", "title": "x", "parentRef": "1001"},
            ),
        ):
            with self.subTest(tool=tool, payload=payload):
                self.assertDenied(self.claude(tool, payload), "protected-items")

    def test_setting_an_unprotected_parent_is_allowed(self) -> None:
        self.approve()
        self.assertAllowed(
            self.claude(
                AZ + "wit_work_item_write",
                {
                    "action": "create",
                    "workItemType": "User Story",
                    "fields": [{"name": "System.Parent", "value": "9001"}],
                },
            )
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
                            "value": (
                                "## &#1001; Origem\n"
                                "Copia da Idea 1001, cor #001001, relacionada a #9001"
                            ),
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

    def test_reading_generated_files_is_allowed(self) -> None:
        # The rule fires on what a command writes, not on the paths it mentions.
        for command in (
            "grep -rn --include=*.g.dart buildWhen lib 2>/dev/null",
            "cat lib/a.g.dart | head -40",
            "ls lib/*.g.dart > /tmp/generated.txt",
            "git diff lib/a.g.dart",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.claude("Bash", {"command": command}))

    def test_shell_writes_to_generated_files_are_denied(self) -> None:
        for command in (
            "echo x > lib/a.g.dart",
            "cp /tmp/a.dart lib/a.g.dart",
            "cd lib\nsed -i 's/a/b/' a.g.dart",
        ):
            with self.subTest(command=command):
                self.assertDenied(
                    self.claude("Bash", {"command": command}), "generated-files"
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

    def test_staged_checks_refuse_different_working_files(self) -> None:
        self.write("security.rules", "staged\n")
        sh(self.repo, "add", "security.rules")
        self.write("security.rules", "unstaged\n")
        checked = subprocess.run(
            [
                sys.executable,
                str(CHECKS),
                "--repo",
                str(self.repo),
                "--staged",
                "--only",
                "rules",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(checked.returncode, 2)
        self.assertIn("staged and working files differ", checked.stderr)
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

    def test_manual_guard_can_be_approved_by_a_tree_bound_button(self) -> None:
        self.write("infra/main.tf")
        sh(self.repo, "add", "infra/main.tf")
        question = "Did you validate the infrastructure change shown above?"
        tool_input = {
            "questions": [
                {
                    "question": question,
                    "header": "Validation",
                    "multiSelect": False,
                    "options": [
                        {
                            "label": "Approve change",
                            "description": "Record my validation for this exact change.",
                        },
                        {"label": "Not now", "description": "Record nothing."},
                    ],
                }
            ]
        }
        self.assertIsNone(
            self.hook(
                "claude",
                "ask",
                {
                    "tool_name": "AskUserQuestion",
                    "tool_use_id": "manual-1",
                    "tool_input": tool_input,
                },
            )
        )
        response = {**tool_input, "answers": {question: "Approve change"}}
        answered = self.hook(
            "claude",
            "answer",
            {
                "tool_name": "AskUserQuestion",
                "tool_use_id": "manual-1",
                "tool_input": response,
                "tool_response": response,
            },
        )
        self.assertIn("manual check infra recorded", str(answered))
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

    def test_feature_story_pr_must_target_its_pinned_feature_branch(self) -> None:
        sessions.start(
            self.repo,
            "1",
            "feature-implementation",
            expected_base_ref="feature/900-parent",
            expected_base_commit=sh(self.repo, "rev-parse", "HEAD").strip(),
        )
        self.assertDenied(
            self.pr(isDraft=True, targetRefName="refs/heads/develop"),
            "feature-branch",
        )

    def test_feature_rule_accepts_a_remote_base_and_skips_unpinned_sessions(
        self,
    ) -> None:
        from harness import rules

        sh(self.repo, "remote", "add", "origin", "https://example.invalid/r.git")
        call = rules.make_call(
            "repo_pull_request_write",
            {"action": "create", "targetRefName": "refs/heads/feature/900-parent"},
            server="azure-devops",
            kind="mcp",
        )
        sessions.start(self.repo, "1", "feature-implementation")
        self.assertTrue(rules.rule_feature_branch(call, self.repo).allowed)
        sessions.transition(self.repo, "close")
        sessions.start(
            self.repo,
            "1",
            "feature-implementation",
            expected_base_ref="origin/feature/900-parent",
        )
        self.assertTrue(rules.rule_feature_branch(call, self.repo).allowed)

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


class TestHistoryPreserved(HookTestCase):
    def test_rewriting_history_is_denied_however_it_is_written(self) -> None:
        # Approval does not override it: this is not a question of permission.
        self.approve()
        for command in (
            "git rebase develop",
            "git rebase -i HEAD~3",
            "git pull --rebase",
            "git pull -r origin develop",
            "git merge --squash userstory/1201-a",
            "git push --force",
            "git push -f origin feature/1200-x",
            "git push -uf origin feature/1200-x",
            "git push --force-with-lease",
            "git push origin +feature/1200-x",
            "git filter-branch --tree-filter 'rm x' HEAD",
            # The forms an agent retries with after a plain one is refused.
            "(git rebase develop)",
            "sudo git push -f",
            "env X=1 git rebase develop",
            "bash -c 'git merge --squash userstory/1201-a'",
            "if true; then git rebase develop; fi",
        ):
            with self.subTest(command=command):
                self.assertDenied(
                    self.claude("Bash", {"command": command}), "history-preserved"
                )

    def test_squash_or_rebase_completion_of_a_pull_request_is_denied(self) -> None:
        self.approve()
        for strategy in ("Squash", "Rebase", "RebaseMerge"):
            with self.subTest(strategy=strategy):
                self.assertDenied(
                    self.claude(
                        AZ + "repo_pull_request_write",
                        {
                            "action": "update",
                            "pullRequestId": 7,
                            "autoComplete": True,
                            "mergeStrategy": strategy,
                        },
                    ),
                    "history-preserved",
                )

    def test_merging_and_ordinary_git_are_allowed(self) -> None:
        self.approve()
        for command in (
            "git merge --no-ff userstory/1201-a",
            "git merge develop",
            "git rebase --abort",
            "git pull",
            "git pull --rebase=false",
            "git log --oneline",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.claude("Bash", {"command": command}))
        self.assertAllowed(
            self.claude(
                AZ + "repo_pull_request_write",
                {
                    "action": "update",
                    "pullRequestId": 7,
                    "mergeStrategy": "NoFastForward",
                },
            )
        )


class TestSettingsValidation(HookTestCase):
    def test_guarded_path_naming_an_unknown_check_fails_closed(self) -> None:
        settings = json.loads((self.repo / ".harness" / "settings.json").read_text())
        settings["guarded_paths"].append(
            {"path": "db/**", "evidence": "check:does-not-exist"}
        )
        (self.repo / ".harness" / "settings.json").write_text(json.dumps(settings))
        self.assertDenied(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")}),
            "harness-error",
        )
        self.assertAllowed(
            self.claude("Read", {"file_path": str(self.repo / "lib/a.dart")})
        )


class TestFailClosed(HookTestCase):
    @staticmethod
    def _hook_module():
        import importlib

        return importlib.import_module("scripts.harness.hook")

    def _in_process(self, tool: str, tool_input: dict) -> dict:
        """Run the hook in this process, so a rule can be made to crash or stall."""
        import contextlib
        import io

        hook = self._hook_module()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hook.handle_pre_tool(
                "claude",
                "pre-tool",
                {"cwd": str(self.repo), "tool_name": tool, "tool_input": tool_input},
            )
        return json.loads(out.getvalue())

    def test_a_crash_in_the_rules_blocks_shell_commands(self) -> None:
        from unittest import mock

        hook = self._hook_module()
        with mock.patch.object(
            hook.rules, "evaluate", side_effect=RuntimeError("boom")
        ):
            result = self._in_process("Bash", {"command": "ls"})
        self.assertDenied(result, "harness-error")

    def test_running_out_of_time_blocks_writes(self) -> None:
        import time
        from unittest import mock

        hook = self._hook_module()
        with (
            mock.patch.object(hook, "RULES_BUDGET_SECONDS", 1),
            mock.patch.object(
                hook.rules, "evaluate", side_effect=lambda *a: time.sleep(3)
            ),
        ):
            result = self._in_process("Write", {"file_path": str(self.repo / "a")})
        self.assertDenied(result, "harness-error")

    def test_a_command_nested_too_deep_to_read_is_blocked(self) -> None:
        self.assertDenied(
            self.claude(
                "Bash", {"command": "eval " * 20 + "cp x .harness/settings.json"}
            ),
            "harness-error",
        )

    def test_a_long_script_is_read_within_the_budget(self) -> None:
        import time

        script = "\n".join(f'cp "$A/f{i}" "$B/"' for i in range(300))
        started = time.monotonic()
        self.assertAllowed(self.claude("Bash", {"command": script}))
        self.assertLess(time.monotonic() - started, 5)

    def test_broken_settings_block_writes_but_not_reads(self) -> None:
        (self.repo / ".harness" / "settings.json").write_text("{not json")
        self.assertDenied(
            self.claude("Write", {"file_path": str(self.repo / "lib/a.dart")}),
            "harness-error",
        )
        self.assertAllowed(
            self.claude("Read", {"file_path": str(self.repo / "lib/a.dart")})
        )


if __name__ == "__main__":
    unittest.main()
