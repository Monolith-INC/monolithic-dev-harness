"""An answer about unchanged content is never asked for twice; menus look the same everywhere."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import decisions, state
from tests.harness.test_decision_answers import type_prompt
from tests.harness.test_decisions import CLI
from tests.settings_fixture import write_settings


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    (tmp_path / "plan.md").write_text("the plan")
    return tmp_path


def present(
    repo: Path, *extra: str, options: tuple[str, ...] = ("Continue", "Revise")
) -> dict:
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--question",
            "Continue with this plan?",
            *(arg for option in options for arg in ("--option", option)),
            "--artifact",
            "plan.md",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


def present_gate(repo: Path, *args: str) -> dict:
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--artifact",
            "plan.md",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


def test_an_answer_about_unchanged_content_is_reused(repo: Path) -> None:
    first = present(repo)
    type_prompt(repo, "1")
    again = present(repo)
    assert again["state"] == "already_answered"
    assert again["decision_id"] == first["decision_id"]
    assert again["answer"] == "Continue"
    assert not decisions.waiting(repo)


def test_changed_content_is_asked_again(repo: Path) -> None:
    present(repo)
    type_prompt(repo, "continue")
    (repo / "plan.md").write_text("a revised plan")
    assert present(repo)["state"] == "waiting_for_human"


def test_a_decline_is_never_reused(repo: Path) -> None:
    present(repo)
    type_prompt(repo, "revise")
    assert present(repo)["state"] == "waiting_for_human"


def test_an_approval_is_reused_until_revoked(repo: Path) -> None:
    gate = (
        "--gate",
        "publish-items",
        "--value",
        "count=3",
        "--value",
        "tracker=Linear",
    )
    shown = present_gate(repo, *gate)
    assert shown["question"] == "Publish these 3 work items to Linear?"
    type_prompt(repo, "approve")
    assert state.active_approval(repo) is not None
    assert present_gate(repo, *gate)["state"] == "already_answered"
    type_prompt(repo, "harness revoke")
    assert present_gate(repo, *gate)["state"] == "waiting_for_human"


def test_an_approval_needs_a_catalog_gate(repo: Path) -> None:
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--question",
            "Publish?",
            "--option",
            "Approve",
            "--option",
            "Not now",
            "--approval",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2 and "--gate" in result.stderr
    assert not decisions.waiting(repo)


def test_chat_menu_numbers_options_with_their_details(repo: Path) -> None:
    shown = present(
        repo,
        "--detail",
        "Hand the plan to backlog drafting.",
        "--recommended",
        "Continue",
        "--allow-free-text",
    )
    assert shown["menu"].splitlines() == [
        "**Continue with this plan?**",
        "",
        "1. **Continue (Recommended)** — Hand the plan to backlog drafting.",
        "2. **Revise**",
        "",
        "Reply with a number, an option name, or tell me what you'd like instead.",
    ]


def test_fallback_keeps_the_same_menu(repo: Path) -> None:
    shown = present(
        repo, "--host", "codex", "--blocking-available", "--detail", "Go on."
    )
    assert shown["transport"] == "blocking"
    result = subprocess.run(
        [str(CLI), "decision", "fallback", "--repo", str(repo), "--host", "codex"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert (
        json.loads(result.stdout)["menu"].splitlines()[2] == "1. **Continue** — Go on."
    )
