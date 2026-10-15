"""Code changes and completion wait for the workflow catalog's requirements.

No Git anywhere: the project is a plain folder, and the local tracker holds the work items.
"""

from __future__ import annotations

import hashlib
import json
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

from core.result import Ok, err
from harness import (
    code_content,
    local_artifacts,
    prepared_workflows,
    settings,
    state,
    work_sessions,
    workflow_requirements,
)
from integrations import registry
from integrations.contracts import ArtifactDraft, LogicalState, WorkItemKind
from scripts import hook_runtime
from scripts.policy import CanonicalToolEvent
from tests.settings_fixture import write_settings

PLAN = 'type: implementation-plan\nstory: "STORY-0001"\nstatus: approved'


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
            WorkItemKind.USER_STORY, "Example", "", ""
        ).value.key
        self.ops.transition_work_item(self.story, LogicalState.IN_PROGRESS)
        self.ops.create_work_item(WorkItemKind.TASK, "Do it", "", self.story)
        self.session = work_sessions.start(self.root, "Build the example").value.id

    def link(self, key: str = "STORY-0001") -> None:
        self.assertIsInstance(work_sessions.link(self.root, self.session, key), Ok)

    def approve_plan_note(self) -> Path:
        plan = self.vault / "Implementation_Plans" / "plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(f"---\n{PLAN}\n---\n\n# Plan\n", encoding="utf-8")
        state.open_approval(self.root, "HB-Q0001", 20)
        state.pin_notes(
            self.root, "HB-Q0001", local_artifacts.approved_notes(self.root)
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
            "---\ntype: adr\nstory: STORY-0001\nstatus: approved\n---\n", "utf-8"
        )
        state.open_approval(self.root, "HB-Q0001", 20)
        state.pin_notes(
            self.root, "HB-Q0001", local_artifacts.approved_notes(self.root)
        )
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_a_plan_edited_after_its_approval_does_not_count(self) -> None:
        self.link()
        plan = self.approve_plan_note()
        plan.write_text(plan.read_text(encoding="utf-8") + "\nOne more step.\n")
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_a_tracker_plan_artifact_counts(self) -> None:
        self.link()
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


class TestBundleApproval(Project):
    """The six-stage confirmation covers the work items its approved bundle names."""

    def approve_bundle(self, story_ref: str = "STORY-0001") -> Path:
        folder = work_sessions.root(self.root) / self.session
        plan = self.root / "docs" / "plan.md"
        drafts = self.root / "docs" / "tracker-drafts.json"
        plan.parent.mkdir(parents=True)
        plan.write_text("the plan\n", encoding="utf-8")
        drafts.write_text(json.dumps({"drafts": []}), encoding="utf-8")
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
        state.write_json(
            folder / "decision.json",
            {
                "status": "answered",
                "approval": True,
                "gate": "implementation-confirm",
                "answer": "Approve",
                "artifacts": [
                    ["docs/plan.md", digest(plan)],
                    ["docs/tracker-drafts.json", digest(drafts)],
                ],
            },
        )
        state.write_json(folder / "tracker-published.json", {"keys": {"S1": story_ref}})
        return plan

    def test_an_approved_unchanged_bundle_that_published_the_story_counts(
        self,
    ) -> None:
        self.link()
        self.approve_bundle()
        self.assertEqual(self.missing(), [])

    def test_a_bundle_that_did_not_publish_this_story_does_not_count(self) -> None:
        self.link()
        self.approve_bundle("STORY-0042")
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_a_bundle_changed_after_approval_does_not_count(self) -> None:
        self.link()
        self.approve_bundle().write_text("changed\n", encoding="utf-8")
        self.assertEqual(self.missing(), ["plan_approved"])

    def test_a_later_revise_answer_withdraws_the_approval(self) -> None:
        self.link()
        self.approve_bundle()
        folder = work_sessions.root(self.root) / self.session
        record = state.read_json(folder / "decision.json")
        state.write_json(folder / "decision-history.json", {"answers": [record]})
        state.write_json(folder / "decision.json", {**record, "answer": "Revise"})
        self.assertEqual(self.missing(), ["plan_approved"])


class TestCatalog(unittest.TestCase):
    def test_every_required_check_is_declared_and_implemented(self) -> None:
        catalog = prepared_workflows.load_catalog()
        declared = set(catalog["requirements"])
        self.assertEqual(declared, workflow_requirements.CHECKED)
        for stage in catalog["stages"].values():
            self.assertLessEqual(set(stage.get("requires", ())), declared)
        self.assertLessEqual(set(catalog["completion"]), declared)
        self.assertEqual(
            catalog["stages"]["execution"]["requires"][0], "work_item_linked"
        )
        self.assertEqual(catalog["completion"][0], "work_item_linked")

    def test_the_implementing_stages_show_the_one_completion_list(self) -> None:
        catalog = prepared_workflows.load_catalog()
        with tempfile.TemporaryDirectory() as directory:
            for route, stage in (
                ("onboarding", "execution"),
                ("implement-approved-item", "verify"),
            ):
                package = prepared_workflows.prepare_stage(
                    Path(directory), route, stage
                ).value
                self.assertEqual(
                    [entry["id"] for entry in package["completion_requirements"]],
                    catalog["completion"],
                )

    def test_the_prepared_step_shows_its_entry_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = prepared_workflows.prepare_stage(
                Path(directory), "onboarding", "execution"
            ).value
        self.assertEqual(
            [entry["id"] for entry in package["entry_requirements"]],
            prepared_workflows.load_catalog()["stages"]["execution"]["requires"],
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
        self.assertIsInstance(
            workflow_requirements.link(self.root, self.session, self.story), Ok
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
        self.assertIn("tdd", self.done().reason)

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
        workflow_requirements.link(self.root, self.session, other)
        workflow_requirements.link(self.root, self.session, self.story)
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])

    def test_a_fresh_work_session_keeps_the_items_baseline(self) -> None:
        self.code("lib/a.dart", "new\n")
        work_sessions.transition(self.root, self.session, "stop")
        self.session = work_sessions.start(self.root, "Again").value.id
        workflow_requirements.link(self.root, self.session, self.story)
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])

    def test_relinking_the_same_item_keeps_the_original_baseline(self) -> None:
        self.code("lib/a.dart", "new\n")
        workflow_requirements.link(self.root, self.session, self.story)
        self.finish()
        self.assertEqual(self.completion(), ["tests_with_code"])

    def test_missing_tracker_reports_stay_open(self) -> None:
        digest = code_content.current(self.root)
        state.record_checks(self.root, digest, [{"name": "unit", "exit_code": 0}])
        state.record_review(self.root, digest, "ready", "fine")
        self.assertEqual(
            self.completion(), ["verification_recorded", "resolution_reported"]
        )

    def test_a_pull_request_is_required_only_with_git_delivery_to_a_remote_host(
        self,
    ) -> None:
        self.finish()
        self.assertEqual(self.completion(), [])
        write_settings(
            self.root,
            artifacts_path="Vault",
            git={"delivery": True},
            checks=[{"name": "unit", "run": "true", "when": ["lib/**"]}],
        )
        self.assertEqual(self.completion(), ["pull_request_linked"])

    def test_another_sessions_item_is_not_completed_here(self) -> None:
        other = self.ops.create_work_item(
            WorkItemKind.USER_STORY, "Other", "", ""
        ).value.key
        self.assertIn("harness work-session link", self.done(other).reason)

    def test_a_task_is_done_inside_its_storys_session(self) -> None:
        self.assertFalse(self.done("TASK-0001").is_denied())
        work_sessions.transition(self.root, self.session, "stop")
        self.assertIn("work session", self.done("TASK-0001").reason)


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
