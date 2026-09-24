import json
import os
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

from host_adapters import (
    format_claude_decision,
    format_cursor_decision,
    parse_claude_payload,
    parse_cursor_payload,
)
from scripts import hook_runtime
from scripts.harness import local_artifacts, state
from scripts.hook_runtime import select_adapter
from scripts.policy import CanonicalToolEvent


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
            config_path = root / ".codex-workflows" / "integrations.json"
            config_path.parent.mkdir()
            config_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "branchTemplate": "{category}/{key}-{slug}",
                        "tracking": {"mode": "skipped"},
                        "tracker": {"adapter": "local_tracker", "bindings": {}},
                        "scm": {"adapter": "github", "connection": {}},
                    }
                ),
                encoding="utf-8",
            )
            event = CanonicalToolEvent(
                client="claude", tool_name="Write", workspace_root=str(root)
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
                            command="git commit -m test",
                            workspace_root=str(root),
                        )
                    ).is_denied()
                )


class _Tracker:
    def __init__(self, artifact_kinds: list[str]):
        self.artifact_kinds = artifact_kinds

    def resolve_branch_key(self, branch: str) -> str:
        return "7824"

    def get_work_item(self, ref: str):
        return mock.Mock(id="7824", key="7824", state=mock.Mock(value="in_progress"))

    def list_artifacts(self, ref: str):
        return [mock.Mock(kind=kind) for kind in self.artifact_kinds]


PLAN = 'type: implementation-plan\nstory: "7824"\nstatus: approved'
ARTIFACT_ENV = ("AGILE_WORKFLOW_ARTIFACTS_PATH", "AGILE_WORKFLOW_ARTIFACTS")


class TestSpecGateArtifactsPath(unittest.TestCase):
    """A note in the artifacts path opens the spec gate only as the user approved it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = self.root / "Vault"
        clean_env = {k: v for k, v in os.environ.items() if k not in ARTIFACT_ENV}
        env = mock.patch.dict(os.environ, clean_env, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.configure("Vault")

    def tearDown(self):
        self._tmp.cleanup()

    def configure(self, artifacts_path: str) -> None:
        """Set the artifacts path where the backlog skills keep it."""
        config = self.root / ".harness" / "backlog" / "config.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            json.dumps({"artifacts_path": artifacts_path}), encoding="utf-8"
        )

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

    def evaluate(self, tracker_kinds: list[str] | None = None):
        config = mock.Mock(tracking_enabled=True, tracker={"adapter": "azure_devops"})
        event = CanonicalToolEvent(
            client="claude",
            tool_name="Write",
            workspace_root=str(self.root),
            branch="userstory/7824-example",
        )
        with (
            mock.patch.object(hook_runtime, "load_config", return_value=config),
            mock.patch.object(
                hook_runtime,
                "tracker_adapter",
                return_value=_Tracker(tracker_kinds or []),
            ),
        ):
            return hook_runtime._evaluate_work_context(event)

    def test_approved_plan_the_user_approved_allows_code_changes(self):
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        self.assertFalse(self.evaluate().is_denied())

    def test_draft_plan_from_the_backlog_stage_denies_even_after_an_approval(self):
        self.note(
            "Implementation_Plans/plan.md",
            'type: implementation-plan\nstory: "7824"\nstatus: draft',
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
        self.note("Specs/spec.md", "type: spec\nticket: 7824\nstatus: approved")
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_work_item_field_names_the_item(self):
        self.note("Specs/spec.md", "type: spec\nwork_item: 7824\nstatus: approved")
        self.approve()
        self.assertFalse(self.evaluate().is_denied())

    def test_every_kind_write_spec_produces_is_accepted(self):
        self.note("Specs/adr.md", "type: adr\nstory: 7824\nstatus: approved")
        self.approve()
        self.assertFalse(self.evaluate().is_denied())

    def test_plan_for_another_story_denies(self):
        self.note(
            "Implementation_Plans/plan.md",
            'type: implementation-plan\nstory: "7825"\nstatus: approved',
        )
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_note_of_another_type_denies(self):
        self.note("Agent_Sessions/s.md", "type: session\nstory: 7824\nstatus: approved")
        self.approve()
        self.assertTrue(self.evaluate().is_denied())

    def test_no_artifacts_path_keeps_the_tracker_only_rule(self):
        self.configure("")
        self.note("Implementation_Plans/plan.md", PLAN)
        self.approve()
        decision = self.evaluate()
        self.assertTrue(decision.is_denied())
        self.assertIn("in the tracker.", decision.reason)

    def test_environment_override_is_honoured(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            self.note("plan.md", PLAN, Path(elsewhere))
            with mock.patch.dict(
                os.environ, {"AGILE_WORKFLOW_ARTIFACTS_PATH": elsewhere}
            ):
                self.approve()
                self.assertFalse(self.evaluate().is_denied())

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
                self.assertFalse(self.evaluate([kind]).is_denied())


if __name__ == "__main__":
    unittest.main()
