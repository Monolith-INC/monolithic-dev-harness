import json
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


class TestSpecGateArtifactsPath(unittest.TestCase):
    def evaluate(
        self,
        *,
        artifacts_path: str,
        notes: dict[str, str],
        tracker_kinds: list[str] | None = None,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".harness").mkdir()
            (root / ".harness" / "policy.json").write_text(
                json.dumps(
                    {"schemaVersion": 1, "backlog": {"artifacts_path": artifacts_path}}
                ),
                encoding="utf-8",
            )
            for name, frontmatter in notes.items():
                note = root / "Vault" / name
                note.parent.mkdir(parents=True, exist_ok=True)
                note.write_text(
                    f"---\n{frontmatter}\n---\n\n# Note\n", encoding="utf-8"
                )
            config = mock.Mock(
                tracking_enabled=True, tracker={"adapter": "azure_devops"}
            )
            event = CanonicalToolEvent(
                client="claude",
                tool_name="Write",
                workspace_root=str(root),
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

    def test_local_plan_naming_the_story_allows_code_changes(self):
        decision = self.evaluate(
            artifacts_path="Vault",
            notes={
                "Implementation_Plans/plan.md": 'type: implementation-plan\nstory: "7824"'
            },
        )
        self.assertFalse(decision.is_denied())

    def test_local_spec_naming_the_ticket_allows_code_changes(self):
        decision = self.evaluate(
            artifacts_path="Vault", notes={"Specs/spec.md": "type: spec\nticket: 7824"}
        )
        self.assertFalse(decision.is_denied())

    def test_local_plan_for_another_story_denies(self):
        decision = self.evaluate(
            artifacts_path="Vault",
            notes={
                "Implementation_Plans/plan.md": 'type: implementation-plan\nstory: "7825"'
            },
        )
        self.assertTrue(decision.is_denied())

    def test_local_note_of_another_type_denies(self):
        decision = self.evaluate(
            artifacts_path="Vault",
            notes={"Agent_Sessions/s.md": "type: session\nticket: 7824"},
        )
        self.assertTrue(decision.is_denied())

    def test_empty_artifacts_path_keeps_the_tracker_only_rule(self):
        decision = self.evaluate(
            artifacts_path="",
            notes={
                "Implementation_Plans/plan.md": 'type: implementation-plan\nstory: "7824"'
            },
        )
        self.assertTrue(decision.is_denied())
        self.assertIn("in the tracker.", decision.reason)

    def test_tracker_artifact_still_allows_without_local_notes(self):
        decision = self.evaluate(
            artifacts_path="Vault", notes={}, tracker_kinds=["implementation_plan"]
        )
        self.assertFalse(decision.is_denied())


if __name__ == "__main__":
    unittest.main()
