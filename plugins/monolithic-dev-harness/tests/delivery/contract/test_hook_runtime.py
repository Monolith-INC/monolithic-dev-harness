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
from harness import (
    local_artifacts,
    sessions,
    settings,
    state,
    work_lifecycle,
    work_sessions,
    workflow_requirements,
)
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
            write_settings(root, git={"delivery": True})
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
    """A git repository on STORY-0001's branch with Git-based delivery; the story is in progress
    with one Task, and a work session is open."""

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
        self.ops.create_work_item(WorkItemKind.TASK, "Do it", "", story.key)
        self.session = work_sessions.start(self.root, "Build the example").value.id

    def configure(self, artifacts_path: str) -> None:
        path = {"artifacts_path": artifacts_path} if artifacts_path else {}
        write_settings(
            self.root,
            branch_template="{category}/{key}-{slug}",
            git={"delivery": True},
            **path,
        )

    def link(self, key: str = "STORY-0001") -> None:
        self.assertIsInstance(work_lifecycle.link(self.root, self.session, key), Ok)

    def evaluate(
        self,
        command: str = "git commit -m wip",
        branch: str = "userstory/STORY-0001-example",
    ):
        """A Git command under Git-based delivery: the code-change requirements, on the item's
        branch (tests/harness/test_workflow_requirements.py covers the requirements)."""
        event = CanonicalToolEvent(
            client="claude",
            tool_name="Bash",
            kind="shell",
            command=command,
            workspace_root=str(self.root),
            branch=branch,
        )
        return hook_runtime._evaluate_git_delivery(event, self.session)


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


class TestGitDeliveryCommits(TrackedRepo):
    """Commits and pushes carry code: the code-change requirements, on the item's own branch."""

    def setUp(self):
        super().setUp()
        self.ops.add_artifact(
            "STORY-0001", ArtifactDraft("implementation_plan", "Plan", "text", "1")
        )

    def test_an_unlinked_work_session_cannot_commit(self):
        decision = self.evaluate()
        self.assertTrue(decision.is_denied())
        self.assertIn("harness work-session link", decision.reason)

    def test_a_ready_work_session_commits_and_pushes_on_its_items_branch(self):
        self.link()
        self.assertFalse(self.evaluate().is_denied())
        self.assertFalse(self.evaluate("git push origin HEAD").is_denied())

    def test_another_items_branch_is_not_covered(self):
        self.link()
        decision = self.evaluate(branch="userstory/STORY-0002-other")
        self.assertIn("STORY-0002", decision.reason)

    def test_a_detached_head_cannot_commit(self):
        self.link()
        self.assertIn("not on a branch", self.evaluate(branch="").reason)

    def test_the_work_item_must_be_in_progress(self):
        self.ops.transition_work_item("STORY-0001", LogicalState.READY)
        self.link()
        self.assertIn("not in progress", self.evaluate().reason)

    def test_a_branch_session_does_not_complete_a_work_item(self):
        """Completion follows the work session's catalog requirements, never the branch."""
        sessions.start(self.root, "STORY-0001", "implement-story")
        for kind in ("resolution_report", "verification", "pull_request"):
            self.ops.add_artifact("STORY-0001", ArtifactDraft(kind, kind, "text", "1"))
        done = CanonicalToolEvent(
            client="claude",
            tool_name="mcp__x__tracker_transition_work_item",
            workspace_root=str(self.root),
        )
        self.assertIn(
            "harness work-session link",
            hook_runtime._evaluate_completion(done, "STORY-0001").reason,
        )
        self.assertIn(
            "local work item not found",
            hook_runtime._evaluate_completion(done, "STORY-0009").reason,
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


PLAN = 'type: implementation-plan\nstory: "STORY-0001"\nstatus: draft'


class TestPlanNotes(TrackedRepo):
    """A note in the artifacts path is the approved plan only as the user approved it."""

    def setUp(self):
        super().setUp()
        self.link()

    def note(self, name: str, frontmatter: str, directory: Path | None = None) -> Path:
        path = (directory or self.vault) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{frontmatter}\n---\n\n# Note\n", encoding="utf-8")
        return path

    def approve(self, approval_id: str = "HB-Q0001") -> None:
        """What the hook does when the user clicks Approve or types `approve HB-…`."""
        state.open_approval(self.root, approval_id, 20)
        state.pin_notes(
            self.root,
            approval_id,
            local_artifacts.reviewed_notes(
                self.root,
                map(
                    str,
                    (local_artifacts.artifacts_dir(self.root) or self.root).rglob(
                        "*.md"
                    ),
                ),
            ),
        )

    def planned(self) -> bool:
        report = workflow_requirements.evaluate(self.root, self.session).value
        return "plan_approved" not in {m.id for m in report.missing}

    def test_approved_plan_the_user_approved_counts(self):
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        self.assertTrue(self.planned())
        self.assertFalse(self.evaluate().is_denied())

    def test_plan_written_after_the_approval_does_not_count(self):
        self.approve()
        self.note("Implementation_Plans/plan.md", PLAN)
        self.assertFalse(self.planned())

    def test_plan_edited_after_the_approval_does_not_count(self):
        plan = self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        plan.write_text(plan.read_text(encoding="utf-8") + "\nOne more step.\n")
        self.assertFalse(self.planned())

    def test_revoked_approval_unpins_the_plan(self):
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        state.revoke_approvals(self.root)
        self.assertFalse(self.planned())

    def test_ticket_field_names_the_parent_and_does_not_count(self):
        self.note(
            "Plans/plan.md",
            "type: implementation-plan\nticket: STORY-0001\nstatus: draft",
        )
        self.approve()
        self.assertFalse(self.planned())

    def test_work_item_field_names_the_item(self):
        self.note(
            "Plans/plan.md",
            "type: implementation-plan\nwork_item: STORY-0001\nstatus: draft",
        )
        self.approve()
        self.assertTrue(self.planned())

    def test_another_spec_kind_is_not_the_implementation_plan(self):
        self.note("Specs/adr.md", "type: adr\nstory: STORY-0001\nstatus: draft")
        self.approve()
        self.assertFalse(self.planned())

    def test_plan_for_another_story_does_not_count(self):
        self.note(
            "Implementation_Plans/plan.md",
            'type: implementation-plan\nstory: "STORY-0002"\nstatus: draft',
        )
        self.approve()
        self.assertFalse(self.planned())

    def test_no_artifacts_path_keeps_the_tracker_only_rule(self):
        self.configure("")
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        self.assertFalse(self.planned())

    def test_home_relative_path_is_expanded(self):
        with tempfile.TemporaryDirectory() as home:
            self.configure("~/vault")
            self.note("plan.md", PLAN, Path(home) / "vault")
            with mock.patch.dict(os.environ, {"HOME": home}):
                self.approve()
                self.assertTrue(self.planned())

    def test_only_an_implementation_plan_artifact_counts_in_the_tracker(self):
        self.ops.add_artifact(
            "STORY-0001", ArtifactDraft("tech-spec", "Spec", "text", "1")
        )
        self.assertFalse(self.planned())
        self.ops.add_artifact(
            "STORY-0001", ArtifactDraft("implementation-plan", "Plan", "text", "1")
        )
        self.assertTrue(self.planned())


if __name__ == "__main__":
    unittest.main()
