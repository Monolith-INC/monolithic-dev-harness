"""A work session shows the user each item once, finished, and asks once.

The draft is written in its type's template and passes validate-artifact before the user is asked
to publish it, so nothing rewrites it after the approval and asks again."""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.result import Err, Ok
from harness import gates, refined
from tests.harness.test_approval_scope import project
from tests.harness.test_bound_approvals import approve
from tests.harness.test_decisions import CLI
from tests.harness.test_plan_review import REFINED

FINISHED = f"""---
type: ticket
work_item_type: User Story
title: Explain what a settings reset removes
story_points: 2
language: en
---

{REFINED}"""

RAW = """---
type: ticket
work_item_type: User Story
title: Explain what a settings reset removes
language: en
---

# Explain what a settings reset removes

## Requirements

- The notice names what a reset removes.

## Acceptance Criteria

- [ ] The notice lists what is removed.
"""


def test_a_finished_story_draft_passes() -> None:
    assert refined.draft_failures(FINISHED) == []


def test_a_raw_story_draft_says_what_is_missing() -> None:
    assert refined.draft_failures(RAW)


def test_documents_that_are_not_items_are_not_held_to_a_template(
    tmp_path: Path,
) -> None:
    (tmp_path / "approach.md").write_text("---\ntype: approach\n---\n\nThe plan.\n")
    (tmp_path / "notes.md").write_text("three stories")
    assert refined.check_drafts(tmp_path, ["approach.md", "notes.md"]) == Ok(None)


def test_check_drafts_names_the_unfinished_draft(tmp_path: Path) -> None:
    (tmp_path / "raw.md").write_text(RAW)
    (tmp_path / "finished.md").write_text(FINISHED)
    result = refined.check_drafts(tmp_path, ["finished.md", "raw.md"])
    assert isinstance(result, Err) and result.failure.code == "draft_not_refined"
    assert "raw.md" in result.failure.message
    assert "finished.md" not in result.failure.message


def _ask_publish(repo: Path, session: str, draft: str) -> subprocess.CompletedProcess:
    subprocess.run(
        [
            str(CLI),
            "workflow",
            "show",
            "--repo",
            str(repo),
            "--session-id",
            session,
            "--artifact",
            draft,
        ],
        capture_output=True,
        timeout=30,
        check=True,
    )
    return subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--session-id",
            session,
            "--gate",
            "publish-items",
            "--value",
            "count=1",
            "--value",
            "items=title:Explain what a settings reset removes",
            "--value",
            "tracker=Local tracker",
            "--artifact",
            draft,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_a_work_session_will_not_ask_to_publish_an_unfinished_draft(
    tmp_path: Path,
) -> None:
    session, _ = project(tmp_path)
    (tmp_path / "raw.md").write_text(RAW)
    asked = _ask_publish(tmp_path, session, "raw.md")
    assert asked.returncode != 0
    assert "Finish the draft before asking to publish it: raw.md" in asked.stderr


def test_a_work_session_asks_once_about_a_finished_draft(tmp_path: Path) -> None:
    session, _ = project(tmp_path)
    (tmp_path / "finished.md").write_text(FINISHED)
    shown = approve(
        tmp_path,
        session,
        "native-a",
        "publish-items",
        "--value",
        "count=1",
        "--value",
        "items=title:Explain what a settings reset removes",
        "--value",
        "tracker=Local tracker",
        "--artifact",
        "finished.md",
    )
    assert shown.get("decision", shown).get("gate", "publish-items") == "publish-items"


def test_the_plan_question_is_an_approval_tied_to_the_plan() -> None:
    (_, catalog) = gates.load().value
    gate = catalog["plan-checkpoint"]
    assert gate.approval and gate.artifact and gate.binds == "artifacts"
    assert gate.options[0].label["en"] == "Approve"
