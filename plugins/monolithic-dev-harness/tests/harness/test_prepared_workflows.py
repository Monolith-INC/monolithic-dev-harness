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

from scripts.harness import prepared_workflows as prepared


class PreparedWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "README.md").write_text("Project overview\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("Project guidance\n", encoding="utf-8")

    def test_every_named_route_has_known_stages(self) -> None:
        route_map = prepared.routes()
        self.assertEqual(
            set(route_map),
            {
                "investigate-request",
                "explore-idea",
                "prepare-artifacts",
                "implement-approved-item",
                "resume-work",
                "suspend-checks",
            },
        )
        self.assertEqual(prepared.stage_ids("suspend-checks"), ("suspend",))

    def test_every_route_stage_has_resolved_knowledge_skills_and_operations(self) -> None:
        packages = tuple(
            prepared.prepare_stage(self.project, route_id, stage_id)
            for route_id, stage_ids in prepared.routes().items()
            for stage_id in stage_ids
        )
        self.assertGreaterEqual(len(packages), 15)
        self.assertTrue(all(package["harness_knowledge"] for package in packages))
        self.assertTrue(all(package["operations"] for package in packages))
        self.assertTrue(all(package["recommended_skills"] for package in packages))

    def test_prepare_returns_project_bound_complete_handoff(self) -> None:
        package = prepared.prepare_stage(
            self.project, "implement-approved-item", "build", original_request="Implement item X"
        )
        self.assertEqual(package["project_root"], str(self.project.resolve()))
        self.assertEqual(package["route"]["stages"], ["setup", "build", "verify"])
        self.assertEqual(package["step"]["id"], "build")
        self.assertTrue(package["digest"])
        self.assertTrue(package["expected_outputs"])
        self.assertTrue(package["checks"])
        self.assertTrue(package["recovery"])
        self.assertEqual(package["original_request"], "Implement item X")

    def test_project_guidance_is_attached_with_digest(self) -> None:
        package = prepared.prepare_stage(self.project, "investigate-request", "discover")
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
        (self.project / "docs" / "README.md").write_text("Product context\n", encoding="utf-8")
        (self.project / "backlog" / "README.md").write_text("Backlog context\n", encoding="utf-8")
        (self.project / "README.md").write_text(
            "See [product](docs/) and [backlog](backlog/).\n", encoding="utf-8"
        )
        package = prepared.prepare_stage(self.project, "investigate-request", "discover")
        project_files = {
            Path(item["path"]).relative_to(self.project.resolve()).as_posix(): item
            for item in package["project_knowledge"]
        }
        self.assertEqual(set(project_files), {"README.md", "AGENTS.md", "docs/README.md", "backlog/README.md"})
        self.assertEqual(project_files["docs/README.md"]["content"], "Product context\n")
        self.assertEqual(project_files["backlog/README.md"]["content"], "Backlog context\n")

    def test_recommended_skill_is_resolved_even_without_manifest(self) -> None:
        package = prepared.prepare_stage(self.project, "explore-idea", "ideate")
        recommendations = {item["name"]: item for item in package["recommended_skills"]}
        idea_skill = recommendations["brainstorm-ideas"]
        self.assertIn("divergent idea generation", idea_skill["description"])
        self.assertIn("Generate a broad", idea_skill["when_to_use"])
        self.assertTrue(Path(idea_skill["instructions"]).is_file())
        self.assertTrue(idea_skill["digest"])

    def test_block_description_is_readable_from_skill_frontmatter(self) -> None:
        package = prepared.prepare_stage(self.project, "prepare-artifacts", "backlog")
        skill = next(item for item in package["recommended_skills"] if item["name"] == "validate-artifact")
        self.assertIn("Validate a single agile artifact", skill["description"])
        self.assertNotEqual(skill["description"], ">")

    def test_harness_knowledge_references_are_resolved_with_digests(self) -> None:
        package = prepared.prepare_stage(self.project, "investigate-request", "discover")
        references = {Path(item["path"]).name for item in package["harness_knowledge"]}
        self.assertEqual(
            references,
            {"workflow-storyboard.md", "technical-discovery.md"},
        )
        self.assertTrue(all(item["digest"] for item in package["harness_knowledge"]))

    def test_adapter_operations_come_from_the_gateway_contract(self) -> None:
        package = prepared.prepare_stage(self.project, "prepare-artifacts", "backlog")
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
        package = prepared.prepare_stage(self.project, "implement-approved-item", "build")
        self.assertIn("active host must confirm", package["host_tool_check"])
        self.assertFalse(package["host_tools_checked"])
        self.assertFalse(package["ready"])

    def test_discovery_requires_exact_original_request(self) -> None:
        package = prepared.prepare_stage(self.project, "investigate-request", "discover")
        self.assertEqual(package["missing_inputs"], ["original_request"])
        self.assertFalse(package["ready"])

    def test_step_is_ready_only_after_host_confirms_each_adapter_operation(self) -> None:
        route, stage = "investigate-request", "discover"
        package = prepared.prepare_stage(
            self.project,
            route,
            stage,
            original_request="Investigate DAY-001 and prepare its plan",
            available_operations=("tracker_describe", "tracker_get_work_item"),
        )
        self.assertFalse(package["ready"])
        self.assertIn("tracker_search_work_items", package["missing_host_operations"])

        ready = prepared.prepare_stage(
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
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "does not exist"):
            prepared.prepare_stage(self.root / "missing", "investigate-request", "discover")

    def test_unknown_route_and_stage_are_rejected(self) -> None:
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "unknown prepared route"):
            prepared.prepare_stage(self.project, "invented", "discover")
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "not part of route"):
            prepared.prepare_stage(self.project, "explore-idea", "build")

    def test_route_listing_is_read_only_even_with_no_project_setup(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "workflow", "routes", "--repo", str(self.project)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("investigate-request", json.loads(result.stdout))
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
                "investigate-request",
                "--prepared-stage",
                "discover",
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
        self.assertIn("knowledge-acquire", {skill["name"] for skill in package["recommended_skills"]})
        self.assertIn("tracker_describe", {tool["name"] for tool in package["operations"]})
        self.assertEqual(package["original_request"], "Investigate DAY-001 and prepare its plan")
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
        return plugin

    def _fixture_catalog(self) -> dict[str, object]:
        return {
            "version": 1,
            "routes": {"sample-route": ["sample-stage"]},
            "stages": {
                "sample-stage": {
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
        catalog["stages"]["sample-stage"]["skills"][0]["name"] = "missing"  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "has no SKILL.md"):
            prepared.prepare_stage(self.project, "sample-route", "sample-stage", plugin_root=plugin)

    def test_missing_knowledge_blocks_preparation(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["sample-stage"]["knowledge"] = ["references/missing.md"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "knowledge is missing"):
            prepared.prepare_stage(self.project, "sample-route", "sample-stage", plugin_root=plugin)

    def test_escaping_knowledge_reference_is_rejected(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["sample-stage"]["knowledge"] = ["../../outside.md"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "escapes"):
            prepared.prepare_stage(self.project, "sample-route", "sample-stage", plugin_root=plugin)

    def test_unknown_operation_blocks_preparation(self) -> None:
        catalog = self._fixture_catalog()
        catalog["stages"]["sample-stage"]["operations"] = ["made_up_tool"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "unknown operation"):
            prepared.prepare_stage(self.project, "sample-route", "sample-stage", plugin_root=plugin)

    def test_bad_route_stage_mapping_is_reported(self) -> None:
        catalog = self._fixture_catalog()
        catalog["routes"]["sample-route"] = ["missing"]  # type: ignore[index]
        plugin = self._fixture_plugin(catalog)
        with self.assertRaisesRegex(prepared.PreparedWorkflowError, "unknown stage"):
            prepared.routes(plugin)

    def test_suspension_route_is_standalone_and_uses_policy_control(self) -> None:
        package = prepared.prepare_stage(self.project, "suspend-checks", "suspend")
        self.assertEqual(package["route"]["stages"], ["suspend"])
        self.assertIn("harness.policies.suspend", {tool["name"] for tool in package["operations"]})


if __name__ == "__main__":
    unittest.main()
