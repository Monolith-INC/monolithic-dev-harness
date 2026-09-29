"""Sessions bind one work item to one checkout; every transition is checked."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok
from harness import sessions
from tests.settings_fixture import write_settings

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts" / "harness" / "cli.py"


def git(root: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


class SessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        git(self.repo, "init", "-q", "-b", "develop")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.repo, "checkout", "-q", "-b", "feature/STORY-0001-x")

    def test_start_records_the_checkout_and_resolves_it(self) -> None:
        session = sessions.start(
            self.repo,
            "STORY-0001",
            "implement-story",
            readiness_state="in_progress",
            readiness_artifacts=("tech_spec",),
        ).value
        self.assertEqual(
            (session.phase, session.checkout.branch),
            (sessions.Phase.ACTIVE, "feature/STORY-0001-x"),
        )
        self.assertEqual(
            session.base_commit, git(self.repo, "rev-parse", "HEAD").strip()
        )
        self.assertEqual(
            (session.readiness_state, session.readiness_artifacts),
            ("in_progress", ("tech_spec",)),
        )
        self.assertEqual(sessions.resolve(self.repo), sessions.Bound(session))

    def test_one_open_session_per_checkout(self) -> None:
        sessions.start(self.repo, "STORY-0001", "implement-story")
        self.assertEqual(
            sessions.start(self.repo, "STORY-0001", "x").failure.code, "session_exists"
        )

    def test_transitions_follow_the_lifecycle(self) -> None:
        sessions.start(self.repo, "STORY-0001", "implement-story")
        self.assertEqual(
            sessions.transition(self.repo, "resume").failure.code, "invalid_transition"
        )
        self.assertEqual(
            sessions.transition(self.repo, "pause").value.phase, sessions.Phase.PAUSED
        )
        self.assertEqual(
            sessions.transition(self.repo, "pause").failure.code, "invalid_transition"
        )
        self.assertEqual(
            sessions.transition(self.repo, "resume").value.phase, sessions.Phase.ACTIVE
        )
        self.assertEqual(
            sessions.transition(self.repo, "close").value.phase, sessions.Phase.CLOSED
        )
        self.assertIsInstance(sessions.resolve(self.repo), sessions.Unbound)
        self.assertEqual(
            sessions.transition(self.repo, "close").failure.code, "no_session"
        )

    def test_a_closed_work_item_can_start_again(self) -> None:
        first = sessions.start(self.repo, "STORY-0001", "implement-story").value
        sessions.transition(self.repo, "close")
        second = sessions.start(self.repo, "STORY-0001", "implement-story").value
        self.assertNotEqual(first.id, second.id)

    def test_events_are_numbered_in_order(self) -> None:
        session = sessions.start(self.repo, "STORY-0001", "implement-story").value
        sessions.transition(self.repo, "pause")
        sessions.transition(self.repo, "resume")
        names = sorted(path.name for path in (session.folder / "events").iterdir())
        self.assertEqual(
            names, ["0001-started.json", "0002-paused.json", "0003-resumed.json"]
        )

    def test_detached_heads_corrupt_records_and_duplicates_are_broken(self) -> None:
        session = sessions.start(self.repo, "STORY-0001", "implement-story").value
        (session.folder / "session.json").write_text("{")
        self.assertIsInstance(sessions.resolve(self.repo), sessions.Broken)
        (session.folder / "session.json").write_text("{}")
        git(self.repo, "checkout", "-q", "--detach")
        self.assertIn("no branch", sessions.resolve(self.repo).reason)
        self.assertIsInstance(sessions.start(self.repo, "STORY-0001", "x"), Err)

    def test_another_checkouts_broken_record_does_not_block_this_one(self) -> None:
        other = self.repo / ".harness" / "state" / "sessions" / "HS-OTHER"
        other.mkdir(parents=True)
        (other / "session.json").write_text(
            json.dumps({"worktree": "/elsewhere", "git_dir": "/x", "branch": "b"})
        )
        self.assertIsInstance(sessions.resolve(self.repo), sessions.Unbound)
        self.assertIsInstance(
            sessions.start(self.repo, "STORY-0001", "implement-story"), Ok
        )
        self.assertIsInstance(sessions.resolve(self.repo), sessions.Bound)

    def test_start_leaves_no_half_written_session(self) -> None:
        session = sessions.start(self.repo, "STORY-0001", "implement-story").value
        self.assertTrue((session.folder / "events" / "0001-started.json").is_file())
        staging = self.repo / ".harness" / "state" / "sessions-staging"
        self.assertEqual(list(staging.iterdir()) if staging.exists() else [], [])

    def test_a_subdirectory_resolves_the_same_checkout(self) -> None:
        sessions.start(self.repo, "STORY-0001", "implement-story")
        (self.repo / "lib").mkdir()
        self.assertIsInstance(sessions.resolve(self.repo / "lib"), sessions.Bound)


class SessionCommandTest(SessionTest):
    """`harness session start` checks the branch carries the work item and the tracker knows it."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args, "--repo", str(self.repo)],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_start_needs_the_branch_to_carry_the_work_item(self) -> None:
        write_settings(self.repo)
        tracker = self.repo / ".harness" / "tracker" / "in_progress"
        tracker.mkdir(parents=True)
        record = {
            "key": "STORY-0001",
            "id": "STORY-0001",
            "title": "t",
            "kind": "user_story",
            "state": "in_progress",
        }
        (tracker / "STORY-0001.json").write_text(json.dumps(record))
        wrong = self.run_cli("session", "start", "STORY-0002")
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("this branch is for STORY-0001", wrong.stderr)
        started = self.run_cli("session", "start", "story-0001")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("STORY-0001 bound to feature/STORY-0001-x", started.stdout)
        self.assertIn("(active)", self.run_cli("session", "status").stdout)
        self.assertIn("paused", self.run_cli("session", "pause").stdout)
        self.assertIsInstance(sessions.resolve(self.repo), sessions.Bound)
        self.assertEqual(self.run_cli("session", "resume").returncode, 0)
        self.assertIsInstance(sessions.start(self.repo, "STORY-0001", "x"), Err)
        self.assertIsInstance(sessions.transition(self.repo, "close"), Ok)

    def test_feature_session_requires_and_verifies_the_feature_base(self) -> None:
        write_settings(self.repo)
        tracker = self.repo / ".harness" / "tracker" / "in_progress"
        tracker.mkdir(parents=True)
        (tracker / "STORY-0001.json").write_text(
            json.dumps(
                {
                    "key": "STORY-0001",
                    "id": "STORY-0001",
                    "title": "t",
                    "kind": "user_story",
                    "state": "in_progress",
                }
            )
        )
        missing = self.run_cli(
            "session", "start", "STORY-0001", "--workflow", "feature-implementation"
        )
        self.assertEqual(missing.returncode, 2)
        self.assertIn("require --base-ref", missing.stderr)
        git(self.repo, "branch", "feature/STORY-0009-parent", "develop")
        git(self.repo, "checkout", "-q", "feature/STORY-0009-parent")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "feature setup")
        git(self.repo, "checkout", "-q", "feature/STORY-0001-x")
        wrong = self.run_cli(
            "session",
            "start",
            "STORY-0001",
            "--workflow",
            "feature-implementation",
            "--base-ref",
            "feature/STORY-0009-parent",
        )
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("was not cut from", wrong.stderr)
        git(self.repo, "branch", "feature/STORY-0008-parent", "HEAD")
        started = self.run_cli(
            "session",
            "start",
            "STORY-0001",
            "--workflow",
            "feature-implementation",
            "--base-ref",
            "feature/STORY-0008-parent",
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        bound = sessions.resolve(self.repo).session
        self.assertEqual(bound.expected_base_ref, "feature/STORY-0008-parent")
