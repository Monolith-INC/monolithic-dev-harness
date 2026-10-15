"""Where work starts and where the idea route may stop are asked, never assumed."""

from __future__ import annotations

import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]


def _flat(relative: str) -> str:
    return " ".join((PLUGIN / relative).read_text(encoding="utf-8").split())


def test_discovery_asks_about_an_already_refined_entry_item() -> None:
    step = _flat("skills/bmad-build/step-01-clarify-and-route.md")
    assert "--gate refined-start" in step
    assert "validate-artifact" in step
    assert "--stage refinement" in step
    assert "Tasks" in step and "not part of refinement" in step


def test_the_idea_route_ends_with_a_choice_to_continue_or_stop() -> None:
    initiative = _flat("skills/plan-initiative/SKILL.md")
    assert "--gate idea-continue" in initiative
    assert "workflow complete" in initiative
    catalog = json.loads((PLUGIN / "config/prepared-workflows.json").read_text())
    assert any(
        "idea-continue" in check for check in catalog["stages"]["ideate"]["checks"]
    )


def test_the_stage_guide_names_both_questions() -> None:
    guide = _flat("references/harness-stage-guide.md")
    assert "refined-start" in guide and "idea-continue" in guide
