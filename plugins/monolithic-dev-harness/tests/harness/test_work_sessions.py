"""Project-linked work sessions are independent of checkout-bound implementation sessions."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok
from harness import work_sessions

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts" / "harness" / "cli.py"


class WorkSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()

    def test_start_keeps_the_request_and_links_directly_to_project(self) -> None:
        result = work_sessions.start(self.project, "  Investigate DAY-001  ")

        self.assertIsInstance(result, Ok)
        session = result.value
        self.assertEqual(session.project_root, self.project.resolve())
        self.assertEqual(session.request, "Investigate DAY-001")
        self.assertEqual(session.status, work_sessions.Status.ACTIVE)
        self.assertTrue((session.folder / "session.json").is_file())

    def test_start_does_not_require_git_tracker_or_project_contract(self) -> None:
        result = work_sessions.start(self.project, "Explore an idea")

        self.assertIsInstance(result, Ok)
        self.assertFalse((self.project / ".harness" / "settings.json").exists())
        self.assertFalse(
            (self.project / ".harness" / "state" / "workflow.json").exists()
        )

    def test_two_tickets_can_have_separate_sessions_in_one_project(self) -> None:
        first = work_sessions.start(self.project, "Investigate DAY-001").value
        second = work_sessions.start(self.project, "Investigate DAY-002").value

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(
            {item.id for item in work_sessions.list_sessions(self.project).value},
            {first.id, second.id},
        )
        self.assertEqual(
            work_sessions.select(self.project, first.id).value.request,
            "Investigate DAY-001",
        )
        self.assertEqual(
            work_sessions.select(self.project, second.id).value.request,
            "Investigate DAY-002",
        )

    def test_lifecycle_is_local_and_keeps_an_ordered_history(self) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value

        paused = work_sessions.transition(self.project, session.id, "pause").value
        stopped = work_sessions.transition(self.project, session.id, "stop").value
        resumed = work_sessions.transition(self.project, session.id, "resume").value

        self.assertEqual(resumed.status, work_sessions.Status.ACTIVE)
        self.assertEqual(
            [event["type"] for event in resumed.events],
            ["started", "paused", "stopped", "resumed"],
        )
        self.assertEqual(paused.status, work_sessions.Status.PAUSED)
        self.assertEqual(stopped.status, work_sessions.Status.STOPPED)
        self.assertFalse(
            (self.project / ".harness" / "state" / "workflow.json").exists()
        )

    def test_stopped_session_needs_an_explicit_resume(self) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value
        stopped = work_sessions.transition(self.project, session.id, "stop").value

        self.assertEqual(
            work_sessions.select(self.project, session.id).value.status,
            work_sessions.Status.STOPPED,
        )
        self.assertEqual(
            work_sessions.transition(self.project, session.id, "pause").failure.code,
            "invalid_transition",
        )
        self.assertEqual(
            work_sessions.transition(self.project, session.id, "resume").value.status,
            work_sessions.Status.ACTIVE,
        )
        self.assertEqual(stopped.status, work_sessions.Status.STOPPED)

    def test_completed_session_is_terminal(self) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value
        completed = work_sessions.transition(self.project, session.id, "complete").value

        self.assertEqual(completed.status, work_sessions.Status.COMPLETE)
        self.assertEqual(
            work_sessions.transition(self.project, session.id, "resume").failure.code,
            "invalid_transition",
        )

    def test_sessions_are_not_visible_from_another_project(self) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value
        other = self.project.parent / "other"
        other.mkdir()

        self.assertEqual(work_sessions.list_sessions(other).value, ())
        self.assertEqual(
            work_sessions.select(other, session.id).failure.code, "session_not_found"
        )

    def test_route_reuses_one_active_exact_request_without_mutating_it(self) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value

        result = work_sessions.route(self.project, "  INVESTIGATE   day-001 ").value

        self.assertEqual(result["action"], "continue_active")
        self.assertEqual(result["session_id"], session.id)
        self.assertEqual(
            work_sessions.select(self.project, session.id).value.events, session.events
        )

    def test_route_asks_before_starting_a_different_request_if_work_is_open(
        self,
    ) -> None:
        work_sessions.start(self.project, "Investigate DAY-001")

        result = work_sessions.route(self.project, "Investigate DAY-002").value

        self.assertEqual(result["action"], "ask_user")
        self.assertIsNone(result["session_id"])
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["candidates"][0]["request"], "Investigate DAY-001")

    def test_route_starts_new_session_when_no_unfinished_session_exists(self) -> None:
        result = work_sessions.route(self.project, "Investigate DAY-001").value

        self.assertEqual(result["action"], "start_new")
        self.assertIsNone(result["session_id"])
        self.assertEqual(result["candidates"], [])

    def test_route_requires_human_choice_for_paused_or_stopped_exact_match(
        self,
    ) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value
        work_sessions.transition(self.project, session.id, "pause")

        result = work_sessions.route(self.project, "Investigate DAY-001").value

        self.assertEqual(result["action"], "ask_user")
        self.assertIsNone(result["session_id"])
        self.assertEqual(result["matches"][0]["status"], "paused")
        self.assertEqual(result["candidates"][0]["id"], session.id)

    def test_route_requires_human_choice_when_duplicate_active_requests_exist(
        self,
    ) -> None:
        first = work_sessions.start(self.project, "Investigate DAY-001").value
        second = work_sessions.start(self.project, "Investigate DAY-001").value

        result = work_sessions.route(self.project, "Investigate DAY-001").value

        self.assertEqual(result["action"], "ask_user")
        self.assertIsNone(result["session_id"])
        self.assertEqual(
            {item["id"] for item in result["matches"]}, {first.id, second.id}
        )

    def test_corrupt_record_is_reported_without_rewriting_it(self) -> None:
        session = work_sessions.start(self.project, "Investigate DAY-001").value
        record = session.folder / "session.json"
        original = "{broken"
        record.write_text(original, encoding="utf-8")

        result = work_sessions.select(self.project, session.id)

        self.assertIsInstance(result, Err)
        self.assertEqual(record.read_text(encoding="utf-8"), original)

    def test_cli_can_start_select_pause_stop_and_resume_without_git(self) -> None:
        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "work-session",
                    *args,
                    "--repo",
                    str(self.project),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

        # CLI onboarding is verified without a session; the session library stays independent.
        from harness import bmad, preferences, setup

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
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"HARNESS_USER_STATE_DIR": str(self.project.parent / "preferences")},
        ):
            self.assertIsInstance(setup.prepare_local_tracker(self.project), Ok)
            self.assertIsInstance(bmad.prepare(self.project, "docs/planning"), Ok)
            self.assertIsInstance(preferences.set_language("en", self.project), Ok)
        started = run("start", "--request", "Investigate DAY-001")
        self.assertEqual(started.returncode, 0, started.stderr)
        session_id = json.loads(started.stdout)["id"]
        active_route = run("route", "--request", "Investigate DAY-001")
        self.assertEqual(json.loads(active_route.stdout)["action"], "continue_active")
        self.assertEqual(run("select", session_id).returncode, 0)
        self.assertEqual(run("pause", session_id).returncode, 0)
        paused_route = json.loads(
            run("route", "--request", "Investigate DAY-001").stdout
        )
        self.assertEqual(paused_route["action"], "ask_user")
        self.assertEqual(paused_route["matches"][0]["status"], "paused")
        self.assertEqual(run("stop", session_id).returncode, 0)
        self.assertEqual(run("resume", session_id).returncode, 0)
        self.assertIn(session_id, run("list").stdout)

    def test_a_session_records_the_mode_it_belongs_to(self) -> None:
        created = work_sessions.create(
            self.project, "discovery mode", mode="discovery", mode_root="EPIC-1"
        ).value

        read = work_sessions.select(self.project, created.id).value

        self.assertEqual((read.mode, read.mode_root), ("discovery", "EPIC-1"))

    def test_a_session_made_for_no_mode_records_none(self) -> None:
        created = work_sessions.create(self.project, "Investigate DAY-001").value

        read = work_sessions.select(self.project, created.id).value

        self.assertEqual((read.mode, read.mode_root), ("", ""))

    def test_recording_mode_lists_the_unended_sessions_that_carry_one(self) -> None:
        plain = work_sessions.create(self.project, "Investigate DAY-001").value
        active = work_sessions.create(self.project, "a mode", mode="one").value
        paused = work_sessions.create(self.project, "b mode", mode="two").value
        stopped = work_sessions.create(self.project, "c mode", mode="three").value
        done = work_sessions.create(self.project, "d mode", mode="four").value
        work_sessions.transition(self.project, paused.id, "pause")
        work_sessions.transition(self.project, stopped.id, "stop")
        work_sessions.transition(self.project, done.id, "complete")

        found = work_sessions.recording_mode(self.project)

        self.assertEqual({session.id for session in found}, {active.id, paused.id})
        self.assertNotIn(plain.id, {session.id for session in found})

    def test_recording_mode_skips_a_session_record_that_cannot_be_read(self) -> None:
        good = work_sessions.create(self.project, "a mode", mode="one").value
        broken = work_sessions.create(self.project, "b mode", mode="two").value
        (broken.folder / "session.json").write_bytes(b"\xff\xfe")

        found = work_sessions.recording_mode(self.project)

        self.assertEqual([session.id for session in found], [good.id])

    def test_recording_mode_needs_no_sessions_folder(self) -> None:
        self.assertEqual(work_sessions.recording_mode(self.project), ())
        self.assertFalse((self.project / ".harness").exists())

    def test_a_session_that_records_a_mode_is_never_a_candidate_for_begin(self) -> None:
        work_sessions.create(self.project, "fixture mode", mode="fixture")

        routed = work_sessions.route(self.project, "add a feature").value

        self.assertEqual(routed["action"], "start_new")
        self.assertEqual(routed["candidates"], [])
        self.assertEqual(routed["matches"], [])

    def test_a_mode_session_is_not_matched_by_its_request_either(self) -> None:
        work_sessions.create(self.project, "fixture mode", mode="fixture")

        routed = work_sessions.route(self.project, "fixture mode").value

        self.assertEqual(routed["action"], "start_new")
        self.assertEqual(routed["matches"], [])

    def test_route_still_offers_the_sessions_a_person_made_beside_a_mode(self) -> None:
        work_sessions.create(self.project, "fixture mode", mode="fixture")
        mine = work_sessions.create(self.project, "Investigate DAY-001").value

        routed = work_sessions.route(self.project, "add a feature").value

        self.assertEqual(routed["action"], "ask_user")
        self.assertEqual([item["id"] for item in routed["candidates"]], [mine.id])

    def test_unmark_takes_the_mode_off_a_session(self) -> None:
        marked = work_sessions.create(
            self.project, "fixture mode", mode="fixture", mode_root="EPIC-1"
        ).value

        result = work_sessions.unmark(self.project, marked.id)

        self.assertIsInstance(result, Ok)
        reread = work_sessions.select(self.project, marked.id).value
        self.assertEqual((reread.mode, reread.mode_root), ("", ""))
        self.assertEqual(reread.status, work_sessions.Status.ACTIVE)
        self.assertEqual(work_sessions.recording_mode(self.project), ())

    def test_a_session_keeps_the_mark_that_it_was_a_mode_session_once_the_mode_is_off(
        self,
    ) -> None:
        marked = work_sessions.create(
            self.project, "fixture mode", mode="fixture", mode_root="EPIC-1"
        ).value
        self.assertTrue(marked.mode_session)

        self.assertIsInstance(work_sessions.unmark(self.project, marked.id), Ok)

        reread = work_sessions.select(self.project, marked.id).value
        self.assertEqual(reread.mode, "")
        self.assertTrue(reread.mode_session)
        self.assertEqual(work_sessions.chosen_among((reread,)), ())

    def test_a_session_made_for_no_mode_never_carries_the_mode_session_mark(
        self,
    ) -> None:
        plain = work_sessions.create(self.project, "Investigate DAY-001").value

        read = work_sessions.select(self.project, plain.id).value

        self.assertFalse(read.mode_session)
        self.assertEqual(work_sessions.chosen_among((read,)), (read,))

    def test_a_left_mode_session_is_neither_a_candidate_nor_a_match_for_begin(
        self,
    ) -> None:
        marked = work_sessions.create(
            self.project, "fixture mode", mode="fixture"
        ).value
        self.assertIsInstance(work_sessions.unmark(self.project, marked.id), Ok)

        routed = work_sessions.route(self.project, "fixture mode").value

        self.assertEqual(routed["action"], "start_new")
        self.assertEqual((routed["matches"], routed["candidates"]), ([], []))

    def test_unmark_leaves_a_session_that_records_no_mode_as_it_is(self) -> None:
        plain = work_sessions.create(self.project, "Investigate DAY-001").value

        self.assertIsInstance(work_sessions.unmark(self.project, plain.id), Ok)

        reread = work_sessions.select(self.project, plain.id).value
        self.assertEqual(reread.events, plain.events)

    def test_unmark_of_a_session_that_is_not_there_is_refused(self) -> None:
        self.assertIsInstance(
            work_sessions.unmark(self.project, "WS-000000000000"), Err
        )


if __name__ == "__main__":
    unittest.main()
