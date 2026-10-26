"""Local edits on the main branch follow the workflow requirements, never the branch."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in os.sys.path:
        os.sys.path.insert(0, str(path))

from harness import local_artifacts, settings, state, work_sessions
from integrations import registry
from integrations.contracts import LogicalState, WorkItemKind
from scripts import hook_runtime
from scripts.policy import CanonicalToolEvent
from tests import route_fixture
from tests.settings_fixture import write_settings


class OptionalVcsExecutionContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "initial",
            ],
            check=True,
        )
        write_settings(self.root, artifacts_path="Vault")
        state.set_tracking_mode(self.root, "enforced")
        self.scope = work_sessions.start(
            self.root, "Implement the approved plan"
        ).value.id
        self.plan = self.root / "Vault" / "Implementation_Plans" / "plan.md"

    def _edit_decision(self):
        return hook_runtime.evaluate_event(
            CanonicalToolEvent(
                client="claude",
                tool_name="Write",
                kind="edit",
                file_path=str(self.root / "lib" / "a.dart"),
                workspace_root=str(self.root),
                branch="main",
            ),
            work_session_id=self.scope,
        )

    def _start_story(self) -> None:
        """A Story in progress with a Task, linked, whose approved plan is pinned."""
        ops = registry.open_selected(self.root, settings.load(self.root)).value
        story = ops.get_work_item(route_fixture.refined_story(ops)).value
        route_fixture.prepared(self.root, ops, story.key, self.plan.parents[1])
        ops.transition_work_item(story.key, LogicalState.IN_PROGRESS)
        ops.create_work_item(WorkItemKind.TASK, "Task", "", story.key)
        work_sessions.link(self.root, self.scope, story.key)
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text(
            f'---\ntype: implementation-plan\nstory: "{story.key}"\nstatus: draft\n'
            "---\n\n# Plan\n",
            encoding="utf-8",
        )
        state.open_approval(self.root, "HB-Q0001", 20)
        state.pin_notes(
            self.root,
            "HB-Q0001",
            local_artifacts.reviewed_notes(
                self.root, map(str, self.root.rglob("*.md"))
            ),
        )

    def test_an_approved_unchanged_plan_allows_local_edit_on_main(self) -> None:
        self._start_story()
        self.assertFalse(self._edit_decision().is_denied())

    def test_the_branch_alone_never_allows_a_local_edit(self) -> None:
        self.assertTrue(self._edit_decision().is_denied())

    def test_a_plan_changed_after_approval_does_not_authorize_local_edit(self) -> None:
        self._start_story()
        self.plan.write_text(
            self.plan.read_text(encoding="utf-8") + "changed\n", encoding="utf-8"
        )
        self.assertTrue(self._edit_decision().is_denied())

    def test_with_git_delivery_a_plan_approval_does_not_commit_on_main(self) -> None:
        write_settings(self.root, artifacts_path="Vault", git={"delivery": True})
        self._start_story()
        event = CanonicalToolEvent(
            client="claude",
            tool_name="Bash",
            kind="shell",
            command="git commit -m unauthorized",
            workspace_root=str(self.root),
            branch="main",
        )
        self.assertTrue(
            hook_runtime._evaluate_git_delivery(event, self.scope).is_denied()
        )


if __name__ == "__main__":
    unittest.main()
