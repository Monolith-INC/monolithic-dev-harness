"""The open question can always be shown again, and the answer to its newest showing counts.

The rc.13 trial lost a dialog's answer, moved the question to the chat, and then had every attempt
to show it again refused. A question is what the user sees, its wording and options, so showing
the same one again is allowed whatever showed it before. Only the newest showing's answer opens
anything: an answer that arrives late from an older dialog changes nothing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness import decisions
from tests.harness.test_decisions import CLI
from tests.harness.test_question_fallback import claude_hook
from tests.settings_fixture import write_settings

QUESTION = "Which list should we start with?"
OPTIONS = ("Tasks", "Notes")


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args, "--repo", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _present(repo: Path) -> dict:
    write_settings(repo)
    shown = _cli(
        repo,
        "decision",
        "present",
        "--host",
        "claude",
        "--blocking-available",
        "--question",
        QUESTION,
        *(part for option in OPTIONS for part in ("--option", option)),
    )
    assert shown.returncode == 0, shown.stderr
    return {"questions": json.loads(shown.stdout)["questions"]}


def _ask(repo: Path, asked: dict, call: str) -> str:
    return claude_hook(
        repo,
        "ask",
        {"tool_name": "AskUserQuestion", "tool_use_id": call, "tool_input": asked},
    )


def _answer(repo: Path, asked: dict, call: str, label: str) -> str:
    answered = {**asked, "answers": {QUESTION: label}}
    return claude_hook(
        repo,
        "answer",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": call,
            "tool_input": answered,
            "tool_response": answered,
        },
    )


def test_a_question_moved_to_the_chat_can_be_shown_in_a_dialog_again(
    tmp_path: Path,
) -> None:
    asked = _present(tmp_path)
    assert "deny" not in _ask(tmp_path, asked, "toolu_1")
    # The dialog's answer never arrives; the agent moves the question to the chat.
    moved = _cli(
        tmp_path, "decision", "fallback", "--host", "claude", "--native-unavailable"
    )
    assert moved.returncode == 0, moved.stderr
    assert decisions.record(tmp_path)["transport"] == "chat"

    assert "deny" not in _ask(tmp_path, asked, "toolu_2")
    _answer(tmp_path, asked, "toolu_2", "Tasks")

    assert not decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == "Tasks"
    assert set(decisions.record(tmp_path)["presented_on"]) == {"blocking", "chat"}


def test_a_question_already_shown_can_be_shown_again(tmp_path: Path) -> None:
    asked = _present(tmp_path)
    _ask(tmp_path, asked, "toolu_1")

    assert "deny" not in _ask(tmp_path, asked, "toolu_2")
    assert decisions.record(tmp_path)["presentation_id"] == "toolu_2"


def test_an_answer_to_an_older_showing_opens_nothing(tmp_path: Path) -> None:
    asked = _present(tmp_path)
    _ask(tmp_path, asked, "toolu_1")
    _ask(tmp_path, asked, "toolu_2")

    late = _answer(tmp_path, asked, "toolu_1", "Notes")

    assert "not recorded" in late
    assert decisions.waiting(tmp_path)
    _answer(tmp_path, asked, "toolu_2", "Tasks")
    assert decisions.record(tmp_path)["answer"] == "Tasks"


def test_a_different_question_is_still_held_while_one_is_open(tmp_path: Path) -> None:
    asked = _present(tmp_path)
    other = {
        "questions": [
            {**asked["questions"][0], "question": "Shall we delete everything?"}
        ]
    }

    assert "decision-pending" in _ask(tmp_path, other, "toolu_1")
    assert decisions.record(tmp_path)["question"] == QUESTION


def test_a_late_answer_to_an_older_dialog_of_an_unprepared_question_opens_nothing(
    tmp_path: Path,
) -> None:
    """A question no command prepared takes its first dialog's id as its own: an answer from
    that first dialog still counts only while it is the newest showing."""
    write_settings(tmp_path)
    asked = {
        "questions": [
            {
                "header": "Start",
                "question": QUESTION,
                "multiSelect": False,
                "options": [{"label": o, "description": f"{o}."} for o in OPTIONS],
            }
        ]
    }
    _ask(tmp_path, asked, "toolu_1")
    _ask(tmp_path, asked, "toolu_2")

    late = _answer(tmp_path, asked, "toolu_1", "Notes")

    assert "not recorded" in late
    assert decisions.waiting(tmp_path)
    _answer(tmp_path, asked, "toolu_2", "Tasks")
    assert decisions.record(tmp_path)["answer"] == "Tasks"
