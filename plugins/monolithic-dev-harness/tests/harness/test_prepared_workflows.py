"""Prepared workflow handoffs resolve to existing, versioned harness material."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts" / "harness" / "cli.py"
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from core.result import Err, Ok
from scripts.harness import prepared_workflows as prepared


class PreparedFailed(Exception):
    """A failed prepared-workflow `Result`, raised so each test reads as before."""


def _value(result):
    match result:
        case Ok(value):
            return value
        case Err(failure):
            raise PreparedFailed(failure.message)


def prepare(*args, git_delivery: bool = False, **kwargs):
    return _value(prepared.prepare_stage(*args, git_delivery=git_delivery, **kwargs))


def routes(*args):
    return _value(prepared.routes(*args))


class PreparedWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "README.md").write_text("Project overview\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("Project guidance\n", encoding="utf-8")

    def test_onboarding_is_the_one_route_family(self) -> None:
        onboarding = (
            "discovery",
            "planning",
            "hardening",
            "refinement",
            "preparation",
            "execution",
            "verify",
        )
        self.assertEqual(
            routes(),
            {"onboarding": onboarding, "explore-idea": ("ideate", *onboarding)},
        )
        self.assertEqual(
            set(prepared.load_catalog()["stages"]), {"ideate", *onboarding}
        )

    def test_refinement_runs_the_backlog_toolkit_against_the_tracker(self) -> None:
        package = prepare(self.project, "onboarding", "refinement")
        self.assertEqual(
            {skill["name"] for skill in package["recommended_skills"]},
            {
                "amend-workitems",
                "validate-artifact",
                "auto-fix-artifact",
                "generate-work-item",
                "enrich-work-item",
                "decompose-backlog",
                "split-story",
                "generate-breakdown-work-items",
                "generate-plain-language-documentation",
            },
        )
        operations = {item["name"] for item in package["operations"]}
        self.assertLessEqual(
            {
                "tracker_create_work_item",
                "tracker_update_work_item",
                "tracker_list_children",
                "tracker_publish_artifact",
            },
            operations,
        )

    def test_the_plan_and_its_tasks_come_from_refinement(self) -> None:
        produced = {
            item["id"]: item["stage"]
            for item in _value(prepared.stage_requirements("execution"))
        }
        self.assertEqual(produced["tasks_parented"], "refinement")
        self.assertEqual(produced["plan_approved"], "refinement")

    def test_verify_completes_the_work_item_and_execution_does_not(self) -> None:
        self.assertFalse(
            prepare(self.project, "onboarding", "execution")["completion_requirements"]
        )
        self.assertTrue(
            prepare(self.project, "onboarding", "verify")["completion_requirements"]
        )

    def test_git_delivery_skills_are_prepared_only_with_git_delivery(self) -> None:
        git_only = {
            "branch-and-pr",
            "review-pr",
            "reconcile-feature-stack",
            "merge-story-stack-into-feature",
            "commit-prep",
            "repository-sync",
        }

        def prepared_skills(git_delivery: bool) -> set[str]:
            return {
                skill["name"]
                for stage in ("execution", "verify")
                for skill in prepare(
                    self.project, "onboarding", stage, git_delivery=git_delivery
                )["recommended_skills"]
            }

        self.assertFalse(git_only & prepared_skills(False))
        self.assertLessEqual(git_only, prepared_skills(True))
        self.assertIn("finish-feature-development", prepared_skills(False))

    def test_every_route_stage_has_resolved_knowledge_skills_and_operations(
        self,
    ) -> None:
        packages = tuple(
            prepare(self.project, route_id, stage_id)
            for route_id, stage_ids in routes().items()
            for stage_id in stage_ids
        )
        self.assertGreaterEqual(len(packages), 15)
        self.assertEqual(
            {package["step"]["id"] for package in packages},
            set(prepared.load_catalog()["stages"]),
        )
        self.assertTrue(all(package["harness_knowledge"] for package in packages))
        self.assertTrue(all(package["operations"] for package in packages))
        self.assertTrue(all(package["recommended_skills"] for package in packages))

    def test_prepare_returns_project_bound_complete_handoff(self) -> None:
        package = prepare(
            self.project,
            "onboarding",
            "execution",
            original_request="Implement item X",
        )
        self.assertEqual(package["project_root"], str(self.project.resolve()))
        self.assertEqual(
            package["route"]["stages"],
            [
                "discovery",
                "planning",
                "hardening",
                "refinement",
                "preparation",
                "execution",
                "verify",
            ],
        )
        self.assertEqual(package["step"]["id"], "execution")
        self.assertTrue(package["digest"])
        self.assertTrue(package["expected_outputs"])
        self.assertTrue(package["checks"])
        self.assertTrue(package["recovery"])
        self.assertEqual(package["original_request"], "Implement item X")

    def test_project_guidance_is_attached_with_digest(self) -> None:
        package = prepare(self.project, "onboarding", "discovery")
        project_files = {
            Path(item["path"]).relative_to(self.project.resolve()).as_posix(): item
            for item in package["project_knowledge"]
        }
        self.assertEqual(
            set(project_files),
            {"README.md", "AGENTS.md"},
        )
        self.assertTrue(all(project_files.values()))

    def test_project_readme_local_links_are_preloaded_once(self) -> None:
        (self.project / "docs").mkdir()
        (self.project / "backlog").mkdir()
        (self.project / "docs" / "README.md").write_text(
            "Product context\n", encoding="utf-8"
        )
        (self.project / "backlog" / "README.md").write_text(
            "Backlog context\n", encoding="utf-8"
        )
        (self.project / "README.md").write_text(
            "See [product](docs/) and [backlog](backlog/).\n", encoding="utf-8"
        )
        package = prepare(self.project, "onboarding", "discovery")
        project_files = {
            Path(item["path"]).relative_to(self.project.resolve()).as_posix(): item
            for item in package["project_knowledge"]
        }
        self.assertEqual(
            set(project_files),
            {"README.md", "AGENTS.md", "docs/README.md", "backlog/README.md"},
        )
        self.assertEqual(
            project_files["docs/README.md"]["content"], "Product context\n"
        )
        self.assertEqual(
            project_files["backlog/README.md"]["content"], "Backlog context\n"
        )

    def test_recommended_skill_is_resolved_even_without_manifest(self) -> None:
        package = prepare(self.project, "explore-idea", "ideate")
        recommendations = {item["name"]: item for item in package["recommended_skills"]}
        idea_skill = recommendations["brainstorm-ideas"]
        self.assertIn("divergent idea generation", idea_skill["description"])
        self.assertIn("Generate a broad", idea_skill["when_to_use"])
        self.assertTrue(Path(idea_skill["instructions"]).is_file())
        self.assertTrue(idea_skill["digest"])

    def test_block_description_is_readable_from_skill_frontmatter(self) -> None:
        package = prepare(self.project, "onboarding", "refinement")
        skill = next(
            item
            for item in package["recommended_skills"]
            if item["name"] == "validate-artifact"
        )
        self.assertIn("Validate a single agile artifact", skill["description"])
        self.assertNotEqual(skill["description"], ">")

    def test_harness_knowledge_references_are_resolved_with_digests(self) -> None:
        package = prepare(self.project, "onboarding", "discovery")
        references = {Path(item["path"]).name for item in package["harness_knowledge"]}
        self.assertEqual(
            references,
            {"onboarding.md", "human-decisions.md", "project-knowledge.md"},
        )
        self.assertTrue(all(item["digest"] for item in package["harness_knowledge"]))

    def test_adapter_operations_come_from_the_gateway_contract(self) -> None:
        package = prepare(self.project, "onboarding", "refinement")
        operation_names = {item["name"] for item in package["operations"]}
        self.assertIn("tracker_describe", operation_names)
        self.assertIn("tracker_create_work_item", operation_names)
        self.assertTrue(
            all(
                item["kind"] == "tracker-or-host-adapter"
                for item in package["operations"]
                if item["name"].startswith(("tracker_", "scm_"))
            )
        )

    def test_handoff_does_not_claim_host_tool_availability(self) -> None:
        package = prepare(self.project, "onboarding", "execution")
        self.assertIn("active host must confirm", package["host_tool_check"])
        self.assertFalse(package["host_tools_checked"])
        self.assertFalse(package["ready"])

    def test_discovery_requires_exact_original_request(self) -> None:
        package = prepare(self.project, "onboarding", "discovery")
        self.assertEqual(package["missing_inputs"], ["original_request"])
        self.assertFalse(package["ready"])

    def test_step_is_ready_only_after_host_confirms_each_adapter_operation(
        self,
    ) -> None:
        route, stage = "onboarding", "discovery"
        package = prepare(
            self.project,
            route,
            stage,
            original_request="Investigate DAY-001 and prepare its plan",
            available_operations=("tracker_describe", "tracker_get_work_item"),
        )
        self.assertFalse(package["ready"])
        self.assertIn("tracker_search_work_items", package["missing_host_operations"])

        ready = prepare(
            self.project,
            route,
            stage,
            original_request="Investigate DAY-001 and prepare its plan",
            available_operations=(
                "tracker_describe",
                "tracker_search_work_items",
                "tracker_get_work_item",
            ),
        )
        self.assertTrue(ready["ready"])
        self.assertEqual(ready["missing_host_operations"], [])

    def test_missing_project_returns_a_clear_error(self) -> None:
        with self.assertRaisesRegex(PreparedFailed, "does not exist"):
            prepare(self.root / "missing", "onboarding", "discovery")

    def test_unknown_route_and_stage_are_rejected(self) -> None:
        with self.assertRaisesRegex(PreparedFailed, "unknown prepared route"):
            prepare(self.project, "invented", "discovery")
        with self.assertRaisesRegex(PreparedFailed, "not part of route"):
            prepare(self.project, "onboarding", "ideate")

    def test_route_listing_is_read_only_even_with_no_project_setup(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "workflow",
                "routes",
                "--repo",
                str(self.project),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("onboarding", json.loads(result.stdout))
        self.assertFalse((self.project / ".harness").exists())

    def test_prepare_cli_includes_skills_and_adapter_operations(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "workflow",
                "prepare",
                "--repo",
                str(self.project),
                "--route",
                "onboarding",
                "--prepared-stage",
                "discovery",
                "--request",
                "Investigate DAY-001 and prepare its plan",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        package = json.loads(result.stdout)
        self.assertIn(
            "knowledge-acquire",
            {skill["name"] for skill in package["recommended_skills"]},
        )
        self.assertIn(
            "tracker_describe", {tool["name"] for tool in package["operations"]}
        )
        self.assertEqual(
            package["original_request"], "Investigate DAY-001 and prepare its plan"
        )
        self.assertFalse((self.project / ".harness").exists())

    def _fixture_plugin(self, catalog: dict[str, object]) -> Path:
        plugin = self.root / "plugin"
        plugin.mkdir()
        (plugin / "config").mkdir()
        (plugin / "references").mkdir()
        (plugin / "skills" / "sample").mkdir(parents=True)
        (plugin / "references" / "known.md").write_text("known\n", encoding="utf-8")
        (plugin / "skills" / "sample" / "SKILL.md").write_text(
            "---\nname: sample\ndescription: Sample skill.\n---\n\nInstructions.\n",
            encoding="utf-8",
        )
        (plugin / "config" / "prepared-workflows.json").write_text(
            json.dumps(catalog), encoding="utf-8"
        )
        (plugin / "config" / "gates.toml").write_text(
            (PLUGIN_ROOT / "config" / "gates.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return plugin

    def _fixture_catalog(self) -> dict[str, object]:
        return {
            "version": 1,
            "facts": {
                "seen": {"kind": "check", "description": "Seen.", "how": "look"},
            },
            "route": [
                {"id": "look", "stage": "discovery", "scope": "work", "done": ["seen"]},
            ],
            "stages": {
                "discovery": {
                    "title": "Sample",
                    "knowledge": ["references/known.md"],
                    "operations": ["harness.doctor"],
                    "skills": [{"name": "sample", "when": "Use for the sample."}],
                    "outputs": ["result"],
                    "checks": ["check result"],
                    "recovery": ["retry safely"],
                }
            },
        }

    def test_missing_recommended_skill_blocks_preparation(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["discovery"]["skills"][0]["name"] = "missing"  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(PreparedFailed, "recommended skill is missing"):
            prepare(self.project, "onboarding", "discovery", plugin_root=plugin)

    def test_missing_knowledge_blocks_preparation(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["discovery"]["knowledge"] = ["references/missing.md"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(PreparedFailed, "knowledge is missing"):
            prepare(self.project, "onboarding", "discovery", plugin_root=plugin)

    def test_escaping_knowledge_reference_is_rejected(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["discovery"]["knowledge"] = ["../../outside.md"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(PreparedFailed, "escapes"):
            prepare(self.project, "onboarding", "discovery", plugin_root=plugin)

    def test_unknown_operation_blocks_preparation(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["discovery"]["operations"] = ["made_up_tool"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(PreparedFailed, "unknown operation"):
            prepare(self.project, "onboarding", "discovery", plugin_root=plugin)

    def test_bad_route_stage_mapping_is_reported(self) -> None:
        catalog = self._fixture_catalog()
        catalog["route"][0]["stage"] = "missing"  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(PreparedFailed, "unknown stage"):
            routes(plugin)


if __name__ == "__main__":
    unittest.main()


def test_the_cli_marks_a_step_ready_once_the_host_confirms_its_tools(
    tmp_path: Path,
) -> None:
    cli = Path(__file__).resolve().parents[2] / "bin" / "harness"
    base = [
        str(cli),
        "workflow",
        "prepare",
        "--route",
        "onboarding",
        "--prepared-stage",
        "discovery",
        "--request",
        "Show both counts",
        "--repo",
        str(tmp_path),
    ]
    unconfirmed = json.loads(
        subprocess.run(base, capture_output=True, text=True, check=True).stdout
    )
    assert unconfirmed["ready"] is False
    needed = [
        tool["name"]
        for tool in unconfirmed["operations"]
        if tool["kind"] == "tracker-or-host-adapter"
    ]
    confirmed = subprocess.run(
        [*base, *(arg for name in needed for arg in ("--available", name))],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(confirmed.stdout)["ready"] is True
