"""Every standard question is documented, and every one the instructions ask exists."""

from __future__ import annotations

import re
from pathlib import Path

from harness import gates, workflow_requirements

PLUGIN = Path(__file__).resolve().parents[3]
CATALOG = gates.load().value[1]
ASKED = re.compile(r"--gate[ =]([a-z][a-z0-9-]*)")


def _instructions() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for folder in ("skills", "references")
        for path in sorted((PLUGIN / folder).rglob("*.md"))
        if "vendor" not in path.parts
    )


def test_every_gate_is_in_the_decisions_reference() -> None:
    reference = (PLUGIN / "references/human-decisions.md").read_text(encoding="utf-8")
    missing = [gate for gate in CATALOG if f"`{gate}`" not in reference]
    assert not missing


def test_every_gate_the_instructions_ask_exists() -> None:
    # `harness workflow requirements --gate` names a requirement list, not a question.
    requirement_lists = set(workflow_requirements.GATES)
    unknown = sorted(
        set(ASKED.findall(_instructions())) - set(CATALOG) - requirement_lists
    )
    assert not unknown
