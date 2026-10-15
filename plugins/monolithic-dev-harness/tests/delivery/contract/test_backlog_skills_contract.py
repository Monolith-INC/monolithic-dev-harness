"""The backlog toolkit's skills run their own approval steps through the harness and its gateway."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[3]
SKILLS = PLUGIN / "skills"
BACKLOG = (
    "generate-work-item",
    "enrich-work-item",
    "decompose-backlog",
    "split-story",
    "generate-breakdown-work-items",
    "amend-workitems",
    "auto-fix-artifact",
    "validate-artifact",
)
PARENT_LINK = re.compile(r"(?:`|\()(\.\./[^`)\s]+?\.(?:md|json|py|toml))")


def _text(skill: str) -> str:
    return " ".join(
        " ".join(path.read_text(encoding="utf-8").split())
        for path in sorted((SKILLS / skill).rglob("*.md"))
    )


@pytest.mark.parametrize("skill", BACKLOG)
def test_no_skill_points_at_the_removed_drafts_flow(skill: str) -> None:
    text = _text(skill)
    for removed in ("tracker-drafts", "tracker publish", "Six-stage preparation mode"):
        assert removed not in text, (skill, removed)


def test_the_breakdown_approves_the_plan_before_any_task() -> None:
    text = " ".join(
        (SKILLS / "generate-breakdown-work-items/SKILL.md").read_text().split()
    )
    assert text.index("implementation-confirm") < text.index(
        "Propose, approve and create"
    )
    assert "This approval is required" in text


@pytest.mark.parametrize("skill", ("decompose-backlog", "split-story"))
def test_a_split_is_approved_with_the_split_question(skill: str) -> None:
    assert "--gate refinement-split" in _text(skill)


@pytest.mark.parametrize(
    "skill",
    ("enrich-work-item", "amend-workitems", "auto-fix-artifact", "split-story"),
)
def test_existing_items_change_through_the_gateway(skill: str) -> None:
    assert "tracker_update_work_item" in _text(skill)


@pytest.mark.parametrize("skill", BACKLOG)
def test_every_parent_relative_reference_resolves(skill: str) -> None:
    missing = [
        f"{path.relative_to(SKILLS)}: {link}"
        for path in (SKILLS / skill).rglob("*.md")
        for link in PARENT_LINK.findall(path.read_text(encoding="utf-8"))
        if "*" not in link
        and "<" not in link
        and not (path.parent / link).resolve().exists()
    ]
    assert not missing
