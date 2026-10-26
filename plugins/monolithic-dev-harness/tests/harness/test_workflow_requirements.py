"""Code changes and completion wait for the workflow catalog's requirements.

No Git anywhere: the project is a plain folder, and the local tracker holds the work items.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.result import Err, Ok, err
from harness import (
    code_content,
    documents,
    local_artifacts,
    prepared_workflows,
    settings,
    state,
    work_lifecycle,
    work_sessions,
    workflow_requirements,
)
from integrations import registry
from integrations.contracts import (
    ArtifactDraft,
    LogicalState,
    WorkItemChanges,
    WorkItemKind,
)
from scripts import hook_runtime
from scripts.policy import CanonicalToolEvent
from tests.harness.test_plan_review import REFINED  # noqa: E402
from tests.settings_fixture import write_settings

PLAN = 'type: implementation-plan\nstory: "STORY-0001"\nstatus: draft'


class Project(unittest.TestCase):
    """A folder without version control; STORY-0001 in progress with one Task under it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.vault = self.root / "Vault"
        write_settings(self.root, artifacts_path="Vault")
        state.set_tracking_mode(self.root, "enforced")
        self.ops = registry.open_selected(self.root, settings.load(self.root)).value
        self.story = self.ops.create_work_item(
            WorkItemKind.USER_STORY,
            "Explain what a settings reset removes",
            REFINED,
            "",
        ).value.key
        self.ops.update_work_item(self.story, WorkItemChanges(story_points=2))
        self.ops.transition_work_item(self.story, LogicalState.IN_PROGRESS)
        self.ops.create_work_item(WorkItemKind.TASK, "Do it", "", self.story)
        self.session = work_sessions.start(self.root, "Build the example").value.id

    def link(self, key: str = "STORY-0001") -> None:
        self.assertIsInstance(work_sessions.link(self.root, self.session, key), Ok)

    def approve_plan_note(self, plan_note: bool = True) -> Path:
        """Approve the Story's plan and its preparation documents, and build its manifest:
        everything the route does for a Story before it starts."""
        plan = self.vault / "Implementation_Plans" / "plan.md"
        if plan_note:
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(f"---\n{PLAN}\n---\n\n# Plan\n", encoding="utf-8")
        for kind in ("risk-assessment", "verification-plan"):
            note = self.vault / "Preparation" / f"{kind}.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(
                f'---\ntype: {kind}\nstory: "STORY-0001"\nstatus: draft\n---\n\n# {kind}\n',
                encoding="utf-8",
            )
        manifest = documents.document_path(
            self.root, self.ops, "STORY-0001", "reading-manifest"
        ).value
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("# Prepared artifact manifest\n", encoding="utf-8")
        state.open_approval(self.root, "HB-Q0001", 20)
        state.pin_notes(
            self.root,
            "HB-Q0001",
            local_artifacts.reviewed_notes(
                self.root, map(str, self.root.rglob("*.md"))
            ),
        )
        return plan

    def report(self) -> workflow_requirements.Report:
        return workflow_requirements.evaluate(self.root, self.session).value

    def missing(self) -> list[str]:
        return [item.id for item in self.report().missing]

    def edit(self, path: str = "lib/a.dart"):
        return hook_runtime.evaluate_event(
            CanonicalToolEvent(
                client="claude",
                tool_name="Write",
                kind="edit",
                file_path=str(self.root / path),
                workspace_root=str(self.root),
            ),
            work_session_id=self.session,
        )


class TestRequirements(Project):
    def test_everything_met_allows_code_changes_without_version_control(self) -> None:
        self.link()
        self.approve_plan_note()
        self.assertEqual(self.missing(), [])
        self.assertFalse(self.edit().is_denied())

    def test_an_unlinked_work_session_needs_its_work_item_first(self) -> None:
        self.approve_plan_note()
        self.assertEqual(self.missing(), ["work_item_linked"])
        decision = self.edit()
        self.assertTrue(decision.is_denied())
        self.assertIn("start-ticket", decision.reason)

    def test_no_work_session_at_all_is_missing_the_link(self) -> None:
        work_sessions.transition(self.root, self.session, "stop")
        report = workflow_requirements.evaluate(self.root, None).value
        self.assertEqual([m.id for m in report.missing], ["work_item_linked"])

    def test_a_story_without_tasks_routes_to_the_breakdown(self) -> None:
        other = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Bare", "", ""
        ).value.key
        self.ops.transition_work_item(other, LogicalState.IN_PROGRESS)
        self.link(other)
        decision = self.edit()
        self.assertIn("tasks_parented", self.missing())
        self.assertIn("generate-breakdown-work-items", decision.reason)

    def test_a_plan_for_another_story_does_not_count(self) -> None:
        self.link()
        plan = self.approve_plan_note()
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("STORY-0001", "STORY-0002")
        )
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_another_spec_kind_is_not_an_implementation_plan(self) -> None:
        self.link()
        note = self.vault / "Specs" / "adr.md"
        note.parent.mkdir(parents=True)
        note.write_text(
            "---\ntype: adr\nstory: STORY-0001\nstatus: draft\n---\n", "utf-8"
        )
        self.approve_plan_note(plan_note=False)
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_a_plan_edited_after_its_approval_does_not_count(self) -> None:
        self.link()
        plan = self.approve_plan_note()
        plan.write_text(plan.read_text(encoding="utf-8") + "\nOne more step.\n")
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_a_tracker_plan_artifact_counts(self) -> None:
        self.link()
        self.approve_plan_note(plan_note=False)
        self.ops.add_artifact(
            self.story, ArtifactDraft("implementation_plan", "Plan", "text", "1")
        )
        self.assertEqual(self.missing(), [])

    def test_the_work_item_must_be_in_progress(self) -> None:
        self.link()
        self.approve_plan_note()
        self.ops.transition_work_item(self.story, LogicalState.READY)
        self.assertEqual(self.missing(), ["work_item_started"])

    def test_a_task_cannot_stand_in_for_its_story(self) -> None:
        self.link("TASK-0001")
        self.assertIn("work_item_started", self.missing())

    def test_an_unknown_work_item_is_a_fact_not_an_outage(self) -> None:
        self.link("STORY-0099")
        report = self.report()
        self.assertEqual(report.unreachable, "")
        self.assertIn("work_item_started", [m.id for m in report.missing])

    def test_an_unreachable_tracker_says_so_and_never_allows(self) -> None:
        self.link()
        self.approve_plan_note()
        with mock.patch.object(
            workflow_requirements.registry,
            "open_selected",
            return_value=err("provider_unavailable", "server not running"),
        ):
            report = self.report()
            decision = self.edit()
        self.assertIn("server not running", report.unreachable)
        self.assertTrue(decision.is_denied())
        self.assertIn("harness suspend", decision.reason)

    def test_tracker_facts_are_reused_while_the_link_holds(self) -> None:
        self.link()
        self.approve_plan_note()
        self.assertEqual(self.missing(), [])
        with mock.patch.object(
            workflow_requirements.registry,
            "open_selected",
            side_effect=AssertionError("tracker contacted"),
        ):
            self.assertEqual(self.missing(), [])
        self.link("STORY-0099")
        self.assertIn("work_item_started", self.missing())

    def test_the_refusal_is_for_the_agent_and_names_the_next_step(self) -> None:
        reason = self.edit().reason
        self.assertIn("not for the user", reason)
        self.assertIn("harness workflow requirements", reason)

    def test_files_outside_code_need_nothing(self) -> None:
        self.assertFalse(self.edit("Vault/notes.md").is_denied())

    def test_skipped_tracking_releases_the_gate(self) -> None:
        state.set_tracking_mode(self.root, "skipped")
        self.assertFalse(self.edit().is_denied())


class TestEntryItem(Project):
    """A work session tracks the item the user started from; its Stories are linked one by one."""

    def tree(self) -> tuple[str, str]:
        feature = self.ops.create_work_item(WorkItemKind.FEATURE, "F", "", "").value.key
        story = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Inside", "", feature
        ).value.key
        return feature, story

    def track(self, key: str):
        return work_lifecycle.track(self.root, self.session, key)

    def test_the_session_records_the_item_the_user_started_from(self) -> None:
        feature, _ = self.tree()
        self.assertEqual(self.track(feature).value.entry_item, feature)
        self.assertEqual(
            work_sessions.select(self.root, self.session).value.entry_item, feature
        )

    def test_a_story_under_the_entry_item_may_be_linked(self) -> None:
        feature, story = self.tree()
        self.track(feature)
        linked = work_lifecycle.link(self.root, self.session, story)
        self.assertEqual(linked.value.work_item, story)

    def test_a_story_outside_the_entry_item_is_refused(self) -> None:
        feature, _ = self.tree()
        self.track(feature)
        refused = work_lifecycle.link(self.root, self.session, self.story)
        self.assertIn(feature, refused.failure.message)

    def test_a_session_tracks_one_entry_item(self) -> None:
        feature, story = self.tree()
        self.track(feature)
        self.assertIsInstance(self.track(story), Err)
        self.assertIsInstance(self.track(feature), Ok)

    def test_a_task_is_not_an_entry_item(self) -> None:
        task = self.ops.list_children(self.story).value[0].key
        self.assertIsInstance(self.track(task), Err)

    def test_relinking_story_by_story_keeps_each_baseline(self) -> None:
        feature, inside = self.tree()
        second = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Second", "", feature
        ).value.key
        self.track(feature)
        work_lifecycle.link(self.root, self.session, inside)
        work_lifecycle.link(self.root, self.session, second)
        self.assertIsNotNone(code_content.baseline(self.root, inside))
        self.assertIsNotNone(code_content.baseline(self.root, second))


class TestCatalog(unittest.TestCase):
    def test_every_guarded_requirement_has_a_check(self) -> None:
        for gate in workflow_requirements.GATES.values():
            for entry in gate.read().value:
                self.assertIn(entry["id"], workflow_requirements.CHECKED, gate.name)

    def test_code_changes_and_completion_start_from_the_link(self) -> None:
        code = [e["id"] for e in workflow_requirements.CODE_CHANGE.read().value]
        done = [e["id"] for e in workflow_requirements.COMPLETION.read().value]
        self.assertIn("work_item_linked", code)
        self.assertEqual(done[: len(code)], code)

    def test_the_implementing_stages_show_the_one_completion_list(self) -> None:
        completion = [e["id"] for e in workflow_requirements.COMPLETION.read().value]
        with tempfile.TemporaryDirectory() as directory:
            for route, stage in (
                ("onboarding", "verify"),
                ("explore-idea", "verify"),
            ):
                package = prepared_workflows.prepare_stage(
                    Path(directory), route, stage, git_delivery=False
                ).value
                self.assertEqual(
                    [entry["id"] for entry in package["completion_requirements"]],
                    completion,
                )

    def test_the_prepared_step_shows_its_entry_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = prepared_workflows.prepare_stage(
                Path(directory), "onboarding", "execution", git_delivery=False
            ).value
        self.assertEqual(
            [entry["id"] for entry in package["entry_requirements"]],
            [e["id"] for e in workflow_requirements.CODE_CHANGE.read().value],
        )


class Verified(Project):
    """STORY-0001 linked with a code baseline; the settings pair lib/ with test/."""

    def setUp(self) -> None:
        super().setUp()
        write_settings(
            self.root,
            artifacts_path="Vault",
            tests_required=[{"source": ["lib/**"], "tests": ["test/**"]}],
            checks=[{"name": "unit", "run": "true", "when": ["lib/**"]}],
            guarded_paths=[{"path": "lib/secure.dart", "evidence": "manual:secure"}],
        )
        self.code("lib/a.dart", "old\n")
        self.approve_plan_note()
        self.assertIsInstance(
            work_lifecycle.link(self.root, self.session, self.story), Ok
        )

    def code(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def completion(self) -> list[str]:
        report = workflow_requirements.evaluate(
            self.root,
            self.session,
            workflow_requirements.COMPLETION,
            work_item=self.story,
        ).value
        return [m.id for m in report.missing]

    def finish(self) -> None:
        """Review, checks, and the tracker artifacts for the code as it is now."""
        digest = code_content.current(self.root)
        state.record_checks(self.root, digest, [{"name": "unit", "exit_code": 0}])
        state.record_review(self.root, digest, "ready", "fine")
        for kind in ("resolution_report", "verification"):
            self.ops.add_artifact(self.story, ArtifactDraft(kind, kind, "text", "1"))

    def done(self, ref: str = "STORY-0001"):
        return hook_runtime.evaluate_event(
            CanonicalToolEvent(
                client="claude",
                tool_name="tracker_transition_work_item",
                arguments={"ref": ref, "state": "done"},
                workspace_root=str(self.root),
            ),
            work_session_id=self.session,
        )


class TestContainerCompletion(Verified):
    """A Feature or Epic is done once every child is done and its closeout is published."""

    def feature(self) -> tuple[str, str]:
        feature = self.ops.create_work_item(WorkItemKind.FEATURE, "F", "", "").value.key
        story = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "S", "", feature
        ).value.key
        return feature, story

    def close(self, ref: str) -> None:
        for kind in ("resolution_report", "verification"):
            self.ops.add_artifact(ref, ArtifactDraft(kind, kind, "evidence", "1"))

    def test_a_feature_with_its_stories_done_and_a_closing_report_is_done(self) -> None:
        feature, story = self.feature()
        self.ops.transition_work_item(story, LogicalState.DONE)
        self.close(feature)
        self.assertFalse(self.done(feature).is_denied())

    def test_an_open_story_keeps_the_feature_open(self) -> None:
        feature, story = self.feature()
        self.close(feature)
        decision = self.done(feature)
        self.assertTrue(decision.is_denied())
        self.assertIn(story, decision.reason)

    def test_a_cancelled_story_does_not_hold_the_feature_open(self) -> None:
        feature, story = self.feature()
        self.ops.transition_work_item(story, LogicalState.CANCELED)
        self.close(feature)
        self.assertFalse(self.done(feature).is_denied())

    def test_the_closeout_is_required(self) -> None:
        feature, story = self.feature()
        self.ops.transition_work_item(story, LogicalState.DONE)
        decision = self.done(feature)
        self.assertTrue(decision.is_denied())
        self.assertIn("resolution_report, verification", decision.reason)

    def test_with_git_delivery_a_feature_closes_without_a_pull_request(self) -> None:
        write_settings(self.root, artifacts_path="Vault", git={"delivery": True})
        feature, story = self.feature()
        self.ops.transition_work_item(story, LogicalState.DONE)
        self.close(feature)
        self.assertFalse(self.done(feature).is_denied())

    def test_a_feature_without_children_is_not_done(self) -> None:
        feature = self.ops.create_work_item(WorkItemKind.FEATURE, "F", "", "").value.key
        self.close(feature)
        self.assertTrue(self.done(feature).is_denied())

    def test_an_epic_closes_on_its_features(self) -> None:
        epic = self.ops.create_work_item(WorkItemKind.EPIC, "E", "", "").value.key
        feature = self.ops.create_work_item(
            WorkItemKind.FEATURE, "F", "", epic
        ).value.key
        self.close(epic)
        self.assertTrue(self.done(epic).is_denied())
        self.ops.transition_work_item(feature, LogicalState.DONE)
        self.assertFalse(self.done(epic).is_denied())


class TestCompletion(Verified):
    def test_tested_checked_reviewed_and_reported_work_is_done(self) -> None:
        self.code("lib/a.dart", "new\n")
        self.code("test/a_test.dart", "covers it\n")
        self.finish()
        self.assertEqual(self.completion(), [])
        self.assertFalse(self.done().is_denied())

    def test_source_changed_without_tests_stays_open(self) -> None:
        self.code("lib/a.dart", "new\n")
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])
        self.assertIn("implement-story", self.done().reason)

    def test_an_edit_after_the_checks_needs_new_evidence(self) -> None:
        self.code("lib/a.dart", "new\n")
        self.code("test/a_test.dart", "covers it\n")
        self.finish()
        self.code("lib/a.dart", "newer\n")
        self.assertEqual(self.completion(), ["checks_passed", "review_ready"])

    def test_a_changed_guarded_path_needs_the_users_confirmation(self) -> None:
        self.code("lib/secure.dart", "risky\n")
        self.code("test/secure_test.dart", "covers it\n")
        self.finish()
        self.assertEqual(self.completion(), ["guarded_paths_verified"])
        state.record_manual(self.root, "secure", code_content.current(self.root), "ok")
        self.assertEqual(self.completion(), [])

    def test_linking_another_item_and_back_keeps_the_original_baseline(self) -> None:
        other = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Other", "", ""
        ).value.key
        self.code("lib/a.dart", "new\n")
        work_lifecycle.link(self.root, self.session, other)
        work_lifecycle.link(self.root, self.session, self.story)
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])

    def test_a_fresh_work_session_keeps_the_items_baseline(self) -> None:
        self.code("lib/a.dart", "new\n")
        work_sessions.transition(self.root, self.session, "stop")
        self.session = work_sessions.start(self.root, "Again").value.id
        work_lifecycle.link(self.root, self.session, self.story)
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])

    def test_relinking_the_same_item_keeps_the_original_baseline(self) -> None:
        self.code("lib/a.dart", "new\n")
        work_lifecycle.link(self.root, self.session, self.story)
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])

    def test_missing_tracker_reports_stay_open(self) -> None:
        digest = code_content.current(self.root)
        state.record_checks(self.root, digest, [{"name": "unit", "exit_code": 0}])
        state.record_review(self.root, digest, "ready", "fine")
        self.assertEqual(
            self.completion(), ["verification_recorded", "resolution_reported"]
        )

    def test_a_pull_request_is_never_required_even_with_git_delivery(self) -> None:
        self.finish()
        write_settings(
            self.root,
            artifacts_path="Vault",
            git={"delivery": True},
            checks=[{"name": "unit", "run": "true", "when": ["lib/**"]}],
        )
        self.assertEqual(self.completion(), [])

    def test_another_sessions_item_is_not_completed_here(self) -> None:
        other = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Other", "", ""
        ).value.key
        self.assertIn("harness work-session link", self.done(other).reason)

    def test_a_task_is_done_inside_its_storys_session(self) -> None:
        self.assertFalse(self.done("TASK-0002").is_denied())
        work_sessions.transition(self.root, self.session, "stop")
        self.assertIn("work session", self.done("TASK-0002").reason)


class TestNoVersionControl(Verified):
    def test_checks_and_review_record_evidence_for_the_code_on_disk(self) -> None:
        from harness import checks, review_verdict

        self.code("lib/a.dart", "new\n")
        self.code("test/a_test.dart", "covers it\n")
        self.assertEqual(checks.main(["--repo", str(self.root)]), 0)
        self.assertEqual(
            review_verdict.main(
                ["--repo", str(self.root), "--verdict", "ready", "--summary", "ok"]
            ),
            0,
        )
        digest = code_content.current(self.root)
        self.assertEqual(state.passed_checks(self.root, digest), {"unit"})
        self.assertEqual(state.review_verdict(self.root, digest), "ready")
        self.assertFalse((self.root / ".git").exists())

    def test_a_check_that_rewrites_code_records_nothing(self) -> None:
        from harness import checks

        script = self.root / "rewrite.py"
        script.write_text(
            "from pathlib import Path\nPath('lib/a.dart').write_text('changed')\n",
            encoding="utf-8",
        )
        write_settings(
            self.root,
            artifacts_path="Vault",
            checks=[{"name": "fmt", "run": f"{sys.executable} {script}"}],
        )
        self.assertEqual(checks.main(["--repo", str(self.root)]), 2)
        self.assertEqual(
            state.passed_checks(self.root, code_content.current(self.root)), set()
        )

    def test_without_code_globs_build_output_is_not_code(self) -> None:
        from harness import checks

        script = self.root / "build_it.py"
        script.write_text(
            "import time\nfrom pathlib import Path\nPath('build').mkdir(exist_ok=True)\n"
            "Path('build/out.txt').write_text(str(time.time()))\n",
            encoding="utf-8",
        )
        write_settings(
            self.root,
            artifacts_path="Vault",
            checks=[{"name": "unit", "run": f"{sys.executable} {script}"}],
        )
        self.assertEqual(checks.main(["--repo", str(self.root)]), 0)
        self.assertEqual(checks.main(["--repo", str(self.root)]), 0)
        self.assertNotIn("build/out.txt", code_content.files(self.root))

    def test_the_project_is_found_by_its_harness_folder(self) -> None:
        from harness import project_paths

        nested = self.root / "lib" / "deep"
        nested.mkdir(parents=True)
        (nested / ".git").mkdir()
        self.assertEqual(project_paths.root(nested), self.root.resolve())


class TestGitDelivery(unittest.TestCase):
    """Rules about Git commands apply only when the user chose Git-based delivery."""

    def event(self, root: Path) -> CanonicalToolEvent:
        return CanonicalToolEvent(
            client="claude",
            tool_name="Bash",
            kind="shell",
            command="git commit -m wip",
            workspace_root=str(root),
        )

    def decision(self, **changes):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_settings(root, **changes)
            state.set_tracking_mode(root, "enforced")
            with mock.patch(
                "policy.git_branch_guard._run_git_cmd", return_value="main"
            ):
                return hook_runtime.evaluate_event(self.event(root))

    def test_without_git_delivery_git_commands_are_the_users_business(self) -> None:
        self.assertFalse(self.decision().is_denied())

    def test_with_git_delivery_the_protected_branch_guard_applies(self) -> None:
        self.assertTrue(self.decision(git={"delivery": True}).is_denied())

    def test_setup_records_git_delivery_only_when_the_user_chooses_it(self) -> None:
        from harness import setup

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_settings(root, artifacts_path="docs")
            unchanged = setup.propose(root).value
            chosen = setup.propose(root, git_delivery=True).value
        self.assertNotIn("delivery", unchanged["git"])
        self.assertIs(chosen["git"]["delivery"], True)
        self.assertTrue(settings.parse(chosen).value.git_delivery)


if __name__ == "__main__":
    unittest.main()
