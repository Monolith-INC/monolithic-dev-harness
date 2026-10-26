"""Rules that were removed stay removed. Each phrase below once told the agent something the
workflow no longer does; when a rule is retired, add its phrase here so it cannot come back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
RETIRED = {
    "agile-backlog-toolkit config --show": "documents get their path from `harness document path`",
    "combined review batch": "each Story's plan is approved alone, then its Tasks (Article 6)",
    "one material review point": "each Story's plan is approved alone, then its Tasks (Article 6)",
    "combined plan-and-Task review": "each Story's plan is approved alone, then its Tasks",
    ".harness/tracker/": "the local tracker is the toolkit's Tickets/ folder",
    "Implementation_Plans/YYYY": "documents are named by document layout, not by date",
    "planning_completion": "the Breakdown Task closes once its Story holds its other Tasks",
    "--next-action": "`harness next` computes the next step; the agent never writes one",
    "workflow checkpoint --stage": "the checkpoint's stage comes from the route",
}


def _agent_facing() -> list[Path]:
    return [
        path
        for folder in ("skills", "references", "common", "config", "hosts", "hooks")
        for path in (PLUGIN / folder).rglob("*")
        if path.is_file() and path.suffix in (".md", ".json", ".toml")
    ]


@pytest.mark.parametrize("phrase", sorted(RETIRED))
def test_a_retired_rule_is_not_back(phrase: str) -> None:
    found = [
        str(path.relative_to(PLUGIN))
        for path in _agent_facing()
        if phrase in path.read_text(encoding="utf-8")
    ]
    assert found == [], f"{phrase!r} is retired: {RETIRED[phrase]}"
