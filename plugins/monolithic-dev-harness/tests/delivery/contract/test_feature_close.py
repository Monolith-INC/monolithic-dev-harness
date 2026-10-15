"""A Feature closes with or without Git-based delivery; locally, only once every Story is done."""

from __future__ import annotations

from pathlib import Path

SKILL = (
    Path(__file__).resolve().parents[3] / "skills/finish-feature-development/SKILL.md"
)


def _sections() -> tuple[str, str]:
    text = " ".join(SKILL.read_text(encoding="utf-8").split())
    local = text.split("## Without Git-based delivery", 1)[1].split("## ", 1)[0]
    git = text.split("## With Git-based delivery", 1)[1].split("## ", 1)[0]
    return local, git


def test_the_local_mode_closes_on_tracker_evidence_alone() -> None:
    local, _ = _sections()
    for needed in ("every Story", "done", "closing evidence", "move-item"):
        assert needed in local
    for git_only in ("pull request", "branch", "merge"):
        assert git_only not in local.casefold()


def test_the_git_mode_keeps_the_stack_and_pull_request() -> None:
    _, git = _sections()
    assert "merge-story-stack-into-feature" in git and "pull request" in git
