"""Workflow checkpoints survive restart without granting external-write permission."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.result import Err, Ok
from harness import bmad, setup, work_sessions
from scripts.harness import preferences, workflow

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts/harness/cli.py"


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def test_navigation_keeps_earlier_points_and_invalidates_later_path(self) -> None:
        started = workflow.start("Build a route guard", "en").value
        one = workflow.add_point(started, "Idea review", "discover").value
        two = workflow.add_point(
            one, "Backlog review", "backlog", completed_writes=("LIN-1",)
        ).value
        self.assertEqual(tuple(point.id for point in two.points), (1, 2, 3))
        earlier = workflow.navigate(two, 2).value
        self.assertEqual(earlier.current.label, "Idea review")
        revised = workflow.add_point(earlier, "Revised idea", "discover").value
        self.assertEqual(
            tuple(point.label for point in revised.points),
            ("First request", "Idea review", "Revised idea"),
        )
        self.assertIn("LIN-1", revised.current.completed_writes)

    def test_pause_resume_cancel_and_invalid_records(self) -> None:
        started = workflow.start("Plan this", "pt-br").value
        self.assertEqual(workflow.pause(started).value.status, "paused")
        self.assertEqual(
            workflow.resume(workflow.pause(started).value).value.status, "active"
        )
        self.assertIsInstance(workflow.resume(workflow.cancel(started).value), Err)
        self.assertIsInstance(workflow.from_dict({"version": 5}), Err)

    def test_save_requires_no_settings_and_excludes_state_from_git(self) -> None:
        started = workflow.start("Plan this", "en").value
        self.assertIsInstance(workflow.save(self.repo, started), Ok)
        self.assertEqual(workflow.load(self.repo), Ok(started))
        self.assertIn(".harness/state/", (self.repo / ".git/info/exclude").read_text())
        self.assertFalse((self.repo / ".harness/settings.json").exists())

    def test_stale_document_is_detected(self) -> None:
        target = self.repo / "plan.md"
        target.write_text("first")
        digest = workflow.file_digest(target).value
        point = workflow.Point(2, "Review", "discover", (("plan.md", digest),))
        self.assertEqual(workflow.stale_artifacts(self.repo, point), ())
        target.write_text("changed")
        self.assertEqual(workflow.stale_artifacts(self.repo, point), ("plan.md",))

    def test_language_preference_is_user_scoped(self) -> None:
        with patch.dict(
            os.environ, {"HARNESS_USER_STATE_DIR": str(Path(self.temp.name) / "user")}
        ):
            self.assertEqual(preferences.language(), Ok(""))
            self.assertIsInstance(preferences.set_language("pt-br"), Ok)
            self.assertEqual(preferences.language(), Ok("pt-br"))
            self.assertFalse((self.repo / ".harness/settings.json").exists())

    def test_cli_starts_pauses_and_resumes_without_reasking_language(self) -> None:
        env = {
            **os.environ,
            "HARNESS_USER_STATE_DIR": str(Path(self.temp.name) / "user"),
        }

        def call(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(CLI), *args, "--repo", str(self.repo)],
                cwd=self.repo,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )

        (self.repo / ".harness").mkdir(exist_ok=True)
        (self.repo / ".harness/settings.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "tracker": {"name": "local"},
                    "scm": {"name": "local"},
                    "branch_template": "{key}-{slug}",
                    "artifacts_path": "docs/planning",
                }
            )
        )
        self.assertIsInstance(setup.prepare_local_tracker(self.repo), Ok)
        self.assertIsInstance(bmad.prepare(self.repo, "docs/planning"), Ok)
        self.assertEqual(call("preference", "language", "en").returncode, 0)
        session = work_sessions.start(self.repo, "Build a route guard").value
        started = call(
            "workflow",
            "start",
            "--request",
            session.request,
            "--session-id",
            session.id,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(
            call("workflow", "pause", "--session-id", session.id).returncode, 0
        )
        resumed = call("workflow", "resume", "--session-id", session.id)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)["status"], "active")
        self.assertEqual(
            call("workflow", "cancel", "--session-id", session.id).returncode, 0
        )
        self.assertNotEqual(
            call("workflow", "resume", "--session-id", session.id).returncode, 0
        )


if __name__ == "__main__":
    unittest.main()
