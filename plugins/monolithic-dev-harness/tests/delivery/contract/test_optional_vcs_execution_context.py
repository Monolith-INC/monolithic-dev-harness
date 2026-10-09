"""An unchanged final approval can scope local edits without a branch-bound session."""

from __future__ import annotations

import hashlib
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

from harness import state, work_sessions, workflow
from scripts import hook_runtime
from scripts.policy import CanonicalToolEvent
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
        write_settings(self.root)
        state.set_tracking_mode(self.root, "enforced")
        self.scope = work_sessions.start(
            self.root, "Implement the approved plan"
        ).value.id
        self.plan = self.root / "docs" / "plan.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("approved plan\n", encoding="utf-8")
        self.digest = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        self._authorize()

    def _authorize(self) -> None:
        current = workflow.start("Implement the approved plan").value
        execution = workflow.add_point(
            current,
            "Execution authorized",
            "execution",
            artifacts=(("docs/plan.md", self.digest),),
        ).value
        workflow.save(self.root, execution, self.scope)
        state.write_json(
            work_sessions.root(self.root) / self.scope / "decision.json",
            {
                "status": "answered",
                "approval": True,
                "gate": "implementation-confirm",
                "answer": "Approve",
                "artifacts": [["docs/plan.md", self.digest]],
            },
        )

    def _edit_decision(self):
        return hook_runtime._evaluate_work_context(
            CanonicalToolEvent(
                client="claude",
                tool_name="Write",
                kind="edit",
                workspace_root=str(self.root),
            )
        )

    def test_approved_unchanged_bundle_allows_local_edit_on_main(self) -> None:
        self.assertFalse(self._edit_decision().is_denied())

    def test_changed_reviewed_artifact_does_not_authorize_local_edit(self) -> None:
        self.plan.write_text("changed after approval\n", encoding="utf-8")
        self.assertTrue(self._edit_decision().is_denied())

    def test_bundle_approval_does_not_authorize_git_commit(self) -> None:
        event = CanonicalToolEvent(
            client="claude",
            tool_name="Bash",
            kind="shell",
            command="git commit -m unauthorized",
            workspace_root=str(self.root),
            branch="main",
        )
        self.assertTrue(hook_runtime._evaluate_work_context(event).is_denied())


if __name__ == "__main__":
    unittest.main()
