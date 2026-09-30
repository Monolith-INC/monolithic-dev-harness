import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.result import Ok
from harness import local_artifacts, sessions, settings, state
from host_adapters import (
    format_claude_decision,
    format_cursor_decision,
    parse_claude_payload,
    parse_cursor_payload,
)
from integrations import registry
from integrations.contracts import ArtifactDraft, LogicalState, WorkItemKind
from scripts import hook_runtime
from scripts.hook_runtime import select_adapter
from scripts.policy import CanonicalToolEvent
from tests.settings_fixture import write_settings


class TestHookRuntime(unittest.TestCase):
    def test_allowed_decision_emits_no_output(self):
        stdout = StringIO()

        with redirect_stdout(stdout):
            hook_runtime.emit_decision("claude", hook_runtime.PolicyDecision.allow())

        self.assertEqual(stdout.getvalue(), "")

    def test_select_adapter_maps_clients_to_expected_handlers(self):
        parser, formatter = select_adapter("claude")
        self.assertIs(parser, parse_claude_payload)
        self.assertIs(formatter, format_claude_decision)

        parser, formatter = select_adapter("cursor")
        self.assertIs(parser, parse_cursor_payload)
        self.assertIs(formatter, format_cursor_decision)

    def test_skipped_tracking_bypasses_ticket_context_checks_but_not_git_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_settings(root)
            state.set_tracking_mode(root, "skipped")
            event = CanonicalToolEvent(
                client="claude",
                tool_name="Write",
                kind="edit",
                workspace_root=str(root),
            )
            self.assertFalse(hook_runtime.evaluate_event(event).is_denied())
            with mock.patch(
                "policy.git_branch_guard._run_git_cmd", return_value="main"
            ):
                self.assertTrue(
                    hook_runtime.evaluate_event(
                        CanonicalToolEvent(
                            client="claude",
                            tool_name="Bash",
                            kind="shell",
                            command="git commit -m test",
                            workspace_root=str(root),
                        )
                    ).is_denied()
                )


def git(root: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, env=env
    )


class TrackedRepo(unittest.TestCase):
    """A git repository on a ticket branch, with the local tracker holding STORY-0001 in progress."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.vault = self.root / "Vault"
        git(self.root, "init", "-q", "-b", "develop")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.root, "checkout", "-q", "-b", "userstory/STORY-0001-example")
        self.configure("Vault")
        self.ops = registry.open_selected(self.root, settings.load(self.root)).value
        story = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Example", "", ""
        ).value
        self.ops.transition_work_item(story.key, LogicalState.IN_PROGRESS)

    def configure(self, artifacts_path: str) -> None:
        path = {"artifacts_path": artifacts_path} if artifacts_path else {}
        write_settings(self.root, branch_template="{category}/{key}-{slug}", **path)

    def evaluate(self):
        event = CanonicalToolEvent(
            client="claude",
            tool_name="Write",
            workspace_root=str(self.root),
            branch="userstory/STORY-0001-example",
        )
        return hook_runtime._evaluate_work_context(event)


class TestBootstrapException(unittest.TestCase):
    def test_only_a_lone_bootstrap_command_skips_the_work_context(self):
        allowed = (
            "python3 /p/scripts/harness/bootstrap.py --repo . --settings-from s.json",
            "harness bootstrap --settings-from s.json",
        )
        refused = (
            "git commit -am wip # workflow-integrations",
            "echo workflow-integrations && git push",
            "python3 /p/scripts/harness/bootstrap.py --repo . && git commit -am x",
            "harness bootstrap; rm -rf lib",
        )
        for command in allowed:
            self.assertTrue(hook_runtime._is_bootstrap_or_repair(command), command)
        for command in refused:
            self.assertFalse(hook_runtime._is_bootstrap_or_repair(command), command)


class TestWorkspace(unittest.TestCase):
    def test_the_hook_checks_the_checkout_the_call_happens_in(self):
        from harness import hook

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "-q", "-b", "develop")
            write_settings(root)
            payload = {
                "cwd": str(root),
                "tool_name": "Write",
                "tool_input": {"file_path": str(root / "a.txt")},
            }
            with (
                mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/elsewhere"}),
                mock.patch.object(hook_runtime, "run", return_value=0) as run,
                mock.patch("scripts.hook_runtime.run", run),
                redirect_stdout(StringIO()),
            ):
                hook.handle_pre_tool("claude", "pre-tool", payload)
            self.assertEqual(Path(run.call_args.args[2]).resolve(), root.resolve())


class TestSessionScope(TrackedRepo):
    """Governed code changes need an active session, and the session names the work item."""

    def setUp(self):
        super().setUp()
        self.ops.add_artifact(
            "STORY-0001", ArtifactDraft("tech_spec", "Spec", "text", "1")
        )

    def test_no_session_denies_and_says_how_to_start_one(self):
        decision = self.evaluate()
        self.assertTrue(decision.is_denied())
        self.assertIn("harness session start", decision.reason)

    def test_an_active_session_allows_and_a_paused_or_closed_one_denies(self):
        self.assertIsInstance(
            sessions.start(self.root, "STORY-0001", "implement-story"), Ok
        )
        self.assertFalse(self.evaluate().is_denied())
        sessions.transition(self.root, "pause")
        self.assertIn("paused", self.evaluate().reason)
        sessions.transition(self.root, "resume")
        self.assertFalse(self.evaluate().is_denied())
        sessions.transition(self.root, "close")
        self.assertTrue(self.evaluate().is_denied())

    def test_the_session_work_item_must_be_in_progress(self):
        self.ops.transition_work_item("STORY-0001", LogicalState.READY)
        sessions.start(self.root, "STORY-0001", "implement-story")
        self.assertIn("must be in progress", self.evaluate().reason)

    def test_ordinary_edits_use_the_start_snapshot_but_push_revalidates(self):
        sessions.start(
            self.root,
            "STORY-0001",
            "implement-story",
            readiness_state="in_progress",
            readiness_artifacts=("tech_spec",),
        )
        self.ops.transition_work_item("STORY-0001", LogicalState.READY)
        with mock.patch.object(
            hook_runtime.registry,
            "open_selected",
            side_effect=AssertionError("tracker"),
        ):
            self.assertFalse(self.evaluate().is_denied())
        pushed = CanonicalToolEvent(
            client="claude",
            tool_name="Bash",
            command="git push origin HEAD",
            workspace_root=str(self.root),
            branch="userstory/STORY-0001-example",
        )
        self.assertIn(
            "must be in progress",
            hook_runtime._evaluate_work_context(pushed).reason,
        )

    def test_a_spec_published_after_session_start_is_found_live(self):
        sessions.start(
            self.root,
            "STORY-0001",
            "implement-story",
            readiness_state="ready",
            readiness_artifacts=(),
        )
        self.assertFalse(self.evaluate().is_denied())

    def test_a_detached_head_cannot_hold_a_session(self):
        sessions.start(self.root, "STORY-0001", "implement-story")
        git(self.root, "checkout", "-q", "--detach")
        self.assertIn("no branch", self.evaluate().reason)

    def test_another_branch_in_the_same_checkout_is_not_covered(self):
        sessions.start(self.root, "STORY-0001", "implement-story")
        git(self.root, "checkout", "-q", "-b", "userstory/STORY-0002-other")
        self.assertTrue(self.evaluate().is_denied())

    def test_completion_is_checked_against_the_session_item(self):
        sessions.start(self.root, "STORY-0001", "implement-story")
        done = CanonicalToolEvent(
            client="claude",
            tool_name="mcp__x__tracker_transition_work_item",
            workspace_root=str(self.root),
        )
        self.assertIn(
            "missing artifacts",
            hook_runtime._evaluate_completion(done, "STORY-0001").reason,
        )
        self.assertIn(
            "its own session",
            hook_runtime._evaluate_completion(done, "STORY-0009").reason,
        )
        for kind in ("resolution_report", "verification", "pull_request"):
            self.ops.add_artifact("STORY-0001", ArtifactDraft(kind, kind, "text", "1"))
        self.assertFalse(
            hook_runtime._evaluate_completion(done, "STORY-0001").is_denied()
        )

    def test_new_branches_follow_the_convention(self):
        self.assertTrue(
            hook_runtime._validate_checkout_convention(
                "git checkout -b feature/nope", str(self.root)
            ).is_denied()
        )
        self.assertFalse(
            hook_runtime._validate_checkout_convention(
                "git switch -c userstory/story-0002-x", str(self.root)
            ).is_denied()
        )


PLAN = 'type: implementation-plan\nstory: "STORY-0001"\nstatus: approved'


class TestSpecGateArtifactsPath(TrackedRepo):
    """A note in the artifacts path opens the spec gate only as the user approved it."""

    def setUp(self):
        super().setUp()
        sessions.start(self.root, "STORY-0001", "implement-story")

    def note(self, name: str, frontmatter: str, directory: Path | None = None) -> Path:
        path = (directory or self.vault) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{frontmatter}\n---\n\n# Note\n", encoding="utf-8")
        return path

    def approve(self, approval_id: str = "HB-Q0001") -> None:
        """What the hook does when the user clicks Approve or types `approve HB-…`."""
        state.open_approval(self.root, approval_id, 20)
        state.pin_notes(
            self.root, approval_id, local_artifacts.approved_notes(self.root)
        )

    def test_approved_plan_the_user_approved_allows_code_changes(self):
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        self.assertFalse(self.evaluate().is_denied())

    def test_draft_plan_from_the_backlog_stage_denies_even_after_an_approval(self):
        self.note(
            "Implementation_Plans/plan.md",
            'type: implementation-plan\nstory: "STORY-0001"\nstatus: draft',
        )
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_plan_marked_approved_without_a_later_approval_denies(self):
        self.approve()
        self.note("Implementation_Plans/plan.md", PLAN)
        decision = self.evaluate()
        self.assertTrue(decision.is_denied())
        self.assertIn("status: approved", decision.reason)

    def test_plan_edited_after_the_approval_denies(self):
        plan = self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        plan.write_text(plan.read_text(encoding="utf-8") + "\nOne more step.\n")
        self.assertTrue(self.evaluate().is_denied())

    def test_revoked_approval_unpins_the_plan(self):
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        state.revoke_approvals(self.root)
        self.assertTrue(self.evaluate().is_denied())

    def test_ticket_field_names_the_parent_and_does_not_count(self):
        self.note("Specs/spec.md", "type: spec\nticket: STORY-0001\nstatus: approved")
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_work_item_field_names_the_item(self):
        self.note(
            "Specs/spec.md", "type: spec\nwork_item: STORY-0001\nstatus: approved"
        )
        self.approve()
        self.assertFalse(self.evaluate().is_denied())

    def test_every_kind_write_spec_produces_is_accepted(self):
        self.note("Specs/adr.md", "type: adr\nstory: STORY-0001\nstatus: approved")
        self.approve()
        self.assertFalse(self.evaluate().is_denied())

    def test_plan_for_another_story_denies(self):
        self.note(
            "Implementation_Plans/plan.md",
            'type: implementation-plan\nstory: "STORY-0002"\nstatus: approved',
        )
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_note_of_another_type_denies(self):
        self.note(
            "Agent_Sessions/s.md", "type: session\nstory: STORY-0001\nstatus: approved"
        )
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_no_artifacts_path_keeps_the_tracker_only_rule(self):
        self.configure("")
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        decision = self.evaluate()
        self.assertTrue(decision.is_denied())
        self.assertIn("in the tracker.", decision.reason)

    def test_home_relative_path_is_expanded(self):
        with tempfile.TemporaryDirectory() as home:
            self.configure("~/vault")
            self.note("plan.md", PLAN, Path(home) / "vault")
            with mock.patch.dict(os.environ, {"HOME": home}):
                self.approve()
                self.assertFalse(self.evaluate().is_denied())

    def test_tracker_artifact_still_allows_without_local_notes(self):
        for kind in ("implementation_plan", "tech-spec", "technical_specification"):
            with self.subTest(kind=kind):
                self.ops.add_artifact(
                    "STORY-0001", ArtifactDraft(kind, kind, "text", "1")
                )
                self.assertFalse(self.evaluate().is_denied())


if __name__ == "__main__":
    unittest.main()
