"""Existing implementation is assessed and materialized without touching its source checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok
from harness import adoption, gitstate
from integrations.contracts import LogicalState, WorkItem, WorkItemKind
from tests.settings_fixture import write_settings

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts" / "harness" / "cli.py"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    ).stdout.strip()


class AdoptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.parent = Path(self._tmp.name)
        self.repo = self.parent / "source"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "develop")
        (self.repo / ".gitignore").write_text(".harness/state/\n")
        write_settings(self.repo)
        (self.repo / "app.txt").write_text("base\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "scratch/STORY-0001")
        (self.repo / "app.txt").write_text("implemented\n")
        git(self.repo, "add", "app.txt")
        git(self.repo, "commit", "-q", "-m", "TASK-0001 inherited implementation")
        (self.repo / "notes.txt").write_text("untracked evidence\n")
        self.story = WorkItem(
            "STORY-0001",
            "STORY-0001",
            "Story",
            WorkItemKind.USER_STORY,
            LogicalState.IN_PROGRESS,
        )
        self.tasks = (
            WorkItem(
                "TASK-0001",
                "TASK-0001",
                "Existing work",
                WorkItemKind.TASK,
                LogicalState.DONE,
            ),
            WorkItem(
                "TASK-0002",
                "TASK-0002",
                "Remaining work",
                WorkItemKind.TASK,
                LogicalState.IN_PROGRESS,
            ),
        )

    def test_assessment_classifies_tasks_without_claiming_unverified_work_done(
        self,
    ) -> None:
        report = adoption.assess(self.repo, self.story, self.tasks, (), "develop").value
        self.assertTrue(report["id"].startswith("HA-"))
        self.assertEqual(
            [task["classification"] for task in report["tasks"]],
            ["unverified", "incomplete"],
        )
        self.assertFalse(report["evidence"]["current"])
        self.assertEqual(report["changes"]["untracked"], ("notes.txt",))
        self.assertTrue(
            (
                self.repo
                / ".harness/state/adoptions"
                / report["id"]
                / "assessment.json"
            ).is_file()
        )

    def test_clean_checkout_classifies_done_task_completed_and_reassesses_idempotently(
        self,
    ) -> None:
        (self.repo / "notes.txt").unlink()
        first = adoption.assess(self.repo, self.story, self.tasks, (), "develop")
        second = adoption.assess(self.repo, self.story, self.tasks, (), "develop")
        self.assertIsInstance(second, Ok)
        self.assertEqual(first.value["id"], second.value["id"])
        self.assertEqual(
            [task["classification"] for task in first.value["tasks"]],
            ["completed", "incomplete"],
        )

    def test_unlabelled_commits_and_uncommitted_paths_are_scope_differences(
        self,
    ) -> None:
        (self.repo / "other.txt").write_text("unrelated\n")
        git(self.repo, "add", "other.txt")
        git(self.repo, "commit", "-q", "-m", "tidy something unrelated")
        report = adoption.assess(self.repo, self.story, self.tasks, (), "develop").value
        self.assertEqual(
            [c["subject"] for c in report["scope_differences"]["unmapped_commits"]],
            ["tidy something unrelated"],
        )
        self.assertEqual(report["scope_differences"]["unmapped_paths"], ("notes.txt",))

    def _approved(self, destination: Path, base_ref: str = "develop") -> dict:
        report = adoption.assess(self.repo, self.story, self.tasks, (), base_ref).value
        plan = adoption.create_plan(
            self.repo, report["id"], "userstory/STORY-0001-adopted", destination
        ).value
        adoption.approve(self.repo, report["id"], plan["digest"], "approved")
        return report

    def test_staged_and_unstaged_tracked_changes_are_transferred(self) -> None:
        (self.repo / "app.txt").write_text("implemented\nstaged\n")
        git(self.repo, "add", "app.txt")
        (self.repo / "app.txt").write_text("implemented\nstaged\nunstaged\n")
        destination = self.parent / "adopted"
        report = self._approved(destination)
        self.assertIsInstance(adoption.materialize(self.repo, report["id"]), Ok)
        self.assertEqual(
            (destination / "app.txt").read_text(), "implemented\nstaged\nunstaged\n"
        )

    def test_moved_base_refuses_the_approved_plan(self) -> None:
        destination = self.parent / "adopted"
        report = self._approved(destination)
        git(self.repo, "checkout", "-q", "develop")
        (self.repo / "later.txt").write_text("later\n")
        git(self.repo, "add", "later.txt")
        git(self.repo, "commit", "-q", "-m", "later")
        git(self.repo, "checkout", "-q", "scratch/STORY-0001")
        failed = adoption.materialize(self.repo, report["id"])
        self.assertIsInstance(failed, Err)
        self.assertIn("moved after assessment", failed.failure.message)
        self.assertFalse(destination.exists())

    def test_conflicting_transfer_rolls_back_the_recovery_worktree(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature/STORY-0000", "develop")
        (self.repo / "app.txt").write_text("feature rewrote this\n")
        git(self.repo, "commit", "-q", "-am", "feature change")
        git(self.repo, "checkout", "-q", "scratch/STORY-0001")
        destination = self.parent / "adopted"
        report = self._approved(destination, "feature/STORY-0000")
        failed = adoption.materialize(self.repo, report["id"])
        self.assertIsInstance(failed, Err)
        self.assertFalse(destination.exists())
        self.assertEqual(
            git(self.repo, "branch", "--list", "userstory/STORY-0001-adopted"), ""
        )

    def test_repeated_materialization_returns_the_recorded_result(self) -> None:
        destination = self.parent / "adopted"
        report = self._approved(destination)
        first = adoption.materialize(self.repo, report["id"]).value
        self.assertEqual(adoption.materialize(self.repo, report["id"]).value, first)

    def test_materialization_requires_exact_plan_approval_and_preserves_source(
        self,
    ) -> None:
        report = adoption.assess(self.repo, self.story, self.tasks, (), "develop").value
        destination = self.parent / "adopted"
        plan = adoption.create_plan(
            self.repo,
            report["id"],
            "userstory/STORY-0001-adopted",
            destination,
        ).value
        self.assertIsInstance(adoption.materialize(self.repo, report["id"]), Err)
        source_before = adoption._fingerprint(self.repo)
        self.assertIsInstance(
            adoption.approve(self.repo, report["id"], plan["digest"], "approved"),
            Ok,
        )
        materialized = adoption.materialize(self.repo, report["id"]).value
        self.assertTrue(destination.is_dir())
        self.assertEqual(
            gitstate.index_tree(destination), gitstate.worktree_tree(self.repo)
        )
        self.assertEqual(adoption._fingerprint(self.repo), source_before)
        self.assertEqual(
            (destination / "notes.txt").read_text(), "untracked evidence\n"
        )
        self.assertEqual(git(destination, "rev-parse", "HEAD"), plan["base_commit"])
        self.assertFalse(materialized["committed"])

    def test_changed_source_invalidates_the_approved_plan(self) -> None:
        report = adoption.assess(self.repo, self.story, self.tasks, (), "develop").value
        plan = adoption.create_plan(
            self.repo,
            report["id"],
            "userstory/STORY-0001-adopted",
            self.parent / "adopted",
        ).value
        adoption.approve(self.repo, report["id"], plan["digest"], "approved")
        (self.repo / "notes.txt").write_text("changed after approval\n")
        failed = adoption.materialize(self.repo, report["id"])
        self.assertIsInstance(failed, Err)
        self.assertIn("source checkout changed", failed.failure.message)

    def test_materialization_preserves_changes_unique_to_the_intended_base(
        self,
    ) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature/STORY-0000", "develop")
        (self.repo / "feature.txt").write_text("feature base\n")
        git(self.repo, "add", "feature.txt")
        git(self.repo, "commit", "-q", "-m", "feature base")
        git(self.repo, "checkout", "-q", "scratch/STORY-0001")
        report = adoption.assess(
            self.repo, self.story, self.tasks, (), "feature/STORY-0000"
        ).value
        destination = self.parent / "feature-adopted"
        plan = adoption.create_plan(
            self.repo,
            report["id"],
            "userstory/STORY-0001-feature-adopted",
            destination,
        ).value
        adoption.approve(self.repo, report["id"], plan["digest"], "approved")
        adoption.materialize(self.repo, report["id"])
        self.assertEqual((destination / "feature.txt").read_text(), "feature base\n")
        self.assertEqual((destination / "app.txt").read_text(), "implemented\n")

    def test_cli_assessment_reads_the_story_and_tasks_from_the_tracker(self) -> None:
        (self.repo / "notes.txt").unlink()
        tracker = self.repo / ".harness/tracker"
        (tracker / "in_progress").mkdir(parents=True)
        (tracker / "done").mkdir(parents=True)
        (tracker / "in_progress/STORY-0001.json").write_text(
            json.dumps(
                {
                    "key": "STORY-0001",
                    "id": "STORY-0001",
                    "title": "Story",
                    "kind": "user_story",
                    "state": "in_progress",
                }
            )
        )
        (tracker / "done/TASK-0001.json").write_text(
            json.dumps(
                {
                    "key": "TASK-0001",
                    "id": "TASK-0001",
                    "title": "Existing work",
                    "kind": "task",
                    "state": "done",
                    "parentId": "STORY-0001",
                }
            )
        )
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "adoption",
                "assess",
                "STORY-0001",
                "--base-ref",
                "develop",
                "--repo",
                str(self.repo),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["work_item"]["key"], "STORY-0001")
        self.assertEqual(report["tasks"][0]["classification"], "completed")
        self.assertEqual(report["changes"]["untracked"], [])

    def test_local_harness_records_are_never_inventoried_or_carried(self) -> None:
        (self.repo / "notes.txt").unlink()
        (self.repo / ".harness/tracker/done").mkdir(parents=True)
        (self.repo / ".harness/tracker/done/TASK-0001.json").write_text("{}\n")
        destination = self.parent / "adopted"
        report = self._approved(destination)
        self.assertEqual(report["changes"]["untracked"], ())
        self.assertEqual(report["tasks"][0]["classification"], "completed")
        self.assertIsInstance(adoption.materialize(self.repo, report["id"]), Ok)
        self.assertFalse((destination / ".harness/tracker").exists())


if __name__ == "__main__":
    unittest.main()
