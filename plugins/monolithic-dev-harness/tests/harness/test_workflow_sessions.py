"""Workflow checkpoints are isolated by project work-session id."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok
from harness import bmad, setup, work_sessions, workflow


class WorkflowSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()

    def start_session(self, request: str) -> work_sessions.Session:
        return work_sessions.start(self.project, request).value

    def test_each_session_has_its_own_checkpoint_file(self) -> None:
        first = self.start_session("Investigate DAY-001")
        second = self.start_session("Investigate DAY-002")
        first_workflow = workflow.start(first.request, "en").value
        second_workflow = workflow.start(second.request, "en").value

        first_path = workflow.save(self.project, first_workflow, first.id).value
        second_path = workflow.save(self.project, second_workflow, second.id).value

        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first_path, first.folder / "workflow.json")
        self.assertEqual(second_path, second.folder / "workflow.json")
        self.assertEqual(
            workflow.load(self.project, first.id).value.request, "Investigate DAY-001"
        )
        self.assertEqual(
            workflow.load(self.project, second.id).value.request, "Investigate DAY-002"
        )

    def test_missing_session_workflow_never_falls_back_to_legacy_project_workflow(
        self,
    ) -> None:
        session = self.start_session("Investigate DAY-001")
        legacy = workflow.start("Legacy request", "en").value
        workflow.save(self.project, legacy)

        result = workflow.load(self.project, session.id)

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "workflow_absent")
        self.assertEqual(workflow.load(self.project).value.request, "Legacy request")

    def test_session_checkpoint_writes_leave_legacy_workflow_unchanged(self) -> None:
        session = self.start_session("Investigate DAY-001")
        legacy = workflow.start("Legacy request", "en").value
        legacy_path = workflow.save(self.project, legacy).value
        original = legacy_path.read_bytes()

        scoped = workflow.start(session.request, "en").value
        workflow.save(self.project, scoped, session.id)

        self.assertEqual(legacy_path.read_bytes(), original)

    def test_unknown_session_cannot_read_or_create_checkpoints(self) -> None:
        result = workflow.save(
            self.project, workflow.start("request", "en").value, "WS-MISSING"
        )

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "session_not_found")
        self.assertFalse(
            (
                self.project / ".harness" / "state" / "work_sessions" / "WS-MISSING"
            ).exists()
        )

    def test_stopped_session_can_be_inspected_but_not_advanced(self) -> None:
        session = self.start_session("Investigate DAY-001")
        saved = workflow.start(session.request, "en").value
        workflow.save(self.project, saved, session.id)
        work_sessions.transition(self.project, session.id, "stop")

        self.assertEqual(
            workflow.load(self.project, session.id).value.request, session.request
        )
        refused = workflow.save(self.project, saved, session.id)
        self.assertIsInstance(refused, Err)
        self.assertEqual(refused.failure.code, "session_not_active")

    def test_cli_can_start_and_read_a_session_scoped_workflow(self) -> None:
        plugin_root = Path(__file__).resolve().parents[2]
        cli = plugin_root / "scripts" / "harness" / "cli.py"

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(cli), *args, "--repo", str(self.project)],
                capture_output=True,
                text=True,
                timeout=30,
                env={
                    **os.environ,
                    "HARNESS_USER_STATE_DIR": str(self.project.parent / "user-state"),
                },
            )

        (self.project / ".harness").mkdir(exist_ok=True)
        (self.project / ".harness/settings.json").write_text(
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
        self.assertIsInstance(setup.prepare_local_tracker(self.project), Ok)
        self.assertIsInstance(bmad.prepare(self.project, "docs/planning"), Ok)
        self.assertEqual(run("preference", "language", "en").returncode, 0)
        session = self.start_session("Investigate DAY-001")
        started = run(
            "workflow",
            "start",
            "--request",
            session.request,
            "--session-id",
            session.id,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        loaded = run("workflow", "status", "--session-id", session.id)
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertEqual(json.loads(loaded.stdout)["request"], session.request)
        self.assertFalse(
            (self.project / ".harness" / "state" / "workflow.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
