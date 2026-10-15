"""Discovery reads knowledge before the repository; each Story's plan is approved before its Tasks."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PLUGIN = ROOT / "plugins" / "monolithic-dev-harness"


class KnowledgeAndPlanOrderTests(unittest.TestCase):
    def test_discovery_routes_catalog_find_fetch_before_repository_reads(self) -> None:
        config = json.loads((PLUGIN / "config/prepared-workflows.json").read_text())
        discovery = config["stages"]["discovery"]
        operations = discovery["operations"]
        self.assertLess(
            operations.index("harness.knowledge.catalog"),
            operations.index("harness.knowledge.find"),
        )
        self.assertLess(
            operations.index("harness.knowledge.find"),
            operations.index("harness.knowledge.fetch"),
        )
        checks = " ".join(discovery["checks"])
        self.assertIn("before broad project reads", checks)
        self.assertIn("never blocks discovery", checks)

    def test_refinement_approves_each_story_plan_before_its_tasks(self) -> None:
        contract = (PLUGIN / "references/onboarding.md").read_text()
        refinement = contract.split("## Refinement", 1)[1].split("## Preparation", 1)[0]
        self.assertLess(
            refinement.index("implementation-confirm"),
            refinement.index("propose the Story's Tasks"),
        )
        self.assertIn("Nothing is approved in bulk", refinement)
        self.assertNotIn("tracker-drafts", contract)
        self.assertNotIn("tracker publish", contract)

    def test_bmad_planning_hands_the_hardened_approach_to_refinement(self) -> None:
        step = " ".join(
            (PLUGIN / "skills/bmad-build/step-02-plan.md").read_text().split()
        )
        self.assertIn("planning approach draft", step)
        self.assertIn("input to the Refinement stage", step)
        self.assertIn("do not start-ticket, inspect Git, or create a branch", step)
        self.assertNotIn("implementation-confirm", step)


if __name__ == "__main__":
    unittest.main()
