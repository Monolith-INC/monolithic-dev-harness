"""Elicitation stays on the decision UI and honors the decision-size limit."""

from pathlib import Path

from harness import gates

PLUGIN = Path(__file__).resolve().parents[2]


def test_advanced_elicitation_requires_paginated_formal_choices() -> None:
    instructions = (PLUGIN / "skills/bmad-advanced-elicitation/SKILL.md").read_text()

    assert "Never print a prose menu and wait for an answer" in instructions
    assert "at most three options" in instructions
    assert "Reshuffle" in instructions
    assert "full catalog" in instructions
    assert "agent recommendations" in instructions
    assert "Proceed" in instructions
    assert "supported fallback for the same" in instructions
    assert "HALT and give the user a choice" not in instructions


def test_confirmation_detail_does_not_assume_tracker_publication() -> None:
    catalog = gates.load().value[1]
    confirm = catalog["implementation-confirm"]
    assert all(
        "tracker" not in option.detail["en"].casefold() for option in confirm.options
    )
    assert all(
        "tracker" not in option.detail["pt-br"].casefold() for option in confirm.options
    )
