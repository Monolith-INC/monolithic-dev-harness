"""A session binds one work item to one exact checkout and moves through a small lifecycle."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.harness import sessions


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


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "app"
        self.repo.mkdir()
        sh(self.repo, "init", "-q", "-b", "develop")
        (self.repo / ".gitignore").write_text(".harness/state/\n")
        sh(self.repo, "add", "-A")
        sh(self.repo, "commit", "-q", "-m", "init")
        sh(self.repo, "checkout", "-q", "-b", "feature/1-demo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def start(self, work_item: str = "1") -> str:
        return str(sessions.start(self.repo, work_item, "delivery")["session_id"])

    def test_a_checkout_without_sessions_is_dormant(self) -> None:
        self.assertEqual(sessions.resolve(self.repo), sessions.Resolution("dormant"))

    def test_a_started_session_is_active_on_its_checkout(self) -> None:
        session_id = self.start()
        resolution = sessions.resolve(self.repo)
        self.assertEqual(
            (resolution.state, resolution.session_id), ("active", session_id)
        )

    def test_a_session_on_another_branch_does_not_apply(self) -> None:
        self.start()
        sh(self.repo, "checkout", "-q", "-b", "feature/2-other")
        self.assertEqual(sessions.resolve(self.repo).state, "dormant")

    def test_pause_resume_and_close_follow_the_lifecycle(self) -> None:
        session_id = self.start()
        sessions.transition(self.repo, session_id, "paused")
        self.assertEqual(sessions.resolve(self.repo).reason, "paused")
        with self.assertRaises(sessions.SessionError):
            sessions.transition(self.repo, session_id, "paused")
        sessions.transition(self.repo, session_id, "resumed")
        self.assertEqual(sessions.resolve(self.repo).state, "active")
        sessions.transition(self.repo, session_id, "closed")
        self.assertEqual(sessions.resolve(self.repo).state, "dormant")

    def test_only_a_paused_session_can_resume(self) -> None:
        session_id = self.start()
        with self.assertRaises(sessions.SessionError):
            sessions.transition(self.repo, session_id, "resumed")

    def test_a_second_session_cannot_start_while_one_is_open(self) -> None:
        self.start("1")
        with self.assertRaises(sessions.SessionError):
            self.start("2")

    def test_a_paused_session_still_holds_the_checkout(self) -> None:
        sessions.transition(self.repo, self.start("1"), "paused")
        with self.assertRaises(sessions.SessionError):
            self.start("2")

    def test_a_closed_session_frees_the_checkout_for_another_work_item(self) -> None:
        sessions.transition(self.repo, self.start("1"), "closed")
        second = self.start("2")
        resolution = sessions.resolve(self.repo)
        self.assertEqual((resolution.state, resolution.session_id), ("active", second))

    def test_the_same_work_item_can_start_again_after_closing(self) -> None:
        first = self.start("1")
        sessions.transition(self.repo, first, "closed")
        second = self.start("1")
        self.assertNotEqual(first, second)
        self.assertEqual(sessions.resolve(self.repo).session_id, second)

    def test_a_closed_session_cannot_be_transitioned(self) -> None:
        session_id = self.start()
        sessions.transition(self.repo, session_id, "closed")
        with self.assertRaises(sessions.SessionError):
            sessions.transition(self.repo, session_id, "resumed")

    def test_a_broken_record_is_reported_instead_of_raised(self) -> None:
        self.start()
        broken = self.repo / sessions.ROOT / "HS-BROKEN" / "session.json"
        broken.parent.mkdir(parents=True)
        broken.write_text("{not json", encoding="utf-8")
        resolution = sessions.resolve(self.repo)
        self.assertEqual(resolution.state, "error")
        self.assertIn("HS-BROKEN", resolution.reason)

    def test_a_session_without_events_is_an_error_not_dormant(self) -> None:
        session_id = self.start()
        for event in (self.repo / sessions.ROOT / session_id / "events").iterdir():
            event.unlink()
        resolution = sessions.resolve(self.repo)
        self.assertEqual(
            (resolution.state, resolution.session_id), ("error", session_id)
        )


if __name__ == "__main__":
    unittest.main()
