"""Regression checks for deterministic discovery routing and six-stage artifact order."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PLUGIN = ROOT / "plugins" / "monolithic-dev-harness"


class KnowledgeAndBundleOrderTests(unittest.TestCase):
    def test_discovery_routes_catalog_find_fetch_before_repository_reads(self) -> None:
        config = json.loads((PLUGIN / "config/prepared-workflows.json").read_text())
        discovery = config["stages"]["discover"]
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

    def test_preparation_contract_places_refined_tracker_drafts_before_final_plan(
        self,
    ) -> None:
        contract = (PLUGIN / "references/six-stage-onboarding.md").read_text()
        preparation = contract.split("## Preparation", 1)[1].split(
            "## Confirmation", 1
        )[0]
        self.assertLess(
            preparation.index("draft every item"),
            preparation.index("write the implementation plan last"),
        )
        self.assertLess(
            preparation.index("draft every item"), preparation.index("manifest over")
        )

    def test_bmad_preparation_preserves_final_plan_order_and_single_confirmation(
        self,
    ) -> None:
        step = (PLUGIN / "skills/bmad-build/step-02-plan.md").read_text()
        self.assertIn("planning approach draft", step)
        self.assertIn("write `{plan_file}` as the final implementation plan", step)
        self.assertIn("do not edit plan/manifest/decision artifacts", step)
        self.assertIn("create a branch during preparation", step.lower())


if __name__ == "__main__":
    unittest.main()
