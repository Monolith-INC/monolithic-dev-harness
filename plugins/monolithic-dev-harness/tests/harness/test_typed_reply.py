"""A typed reply answers the open question, but only in a conversation that was shown it.

In the rc.13 trial the user typed "1", then "Aprovar" twice, after the dialog's answer was lost.
A typed reply counts whatever showed the question (a dialog, then the chat), as long as it was
shown in this conversation. A "1" typed in another conversation, or before the question ever
reached the user, answers nothing, and is read as an ordinary message.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness import decisions
from tests.harness.test_present_again import _cli
from tests.harness.test_question_fallback import claude_hook
from tests.settings_fixture import write_settings

QUESTION = "Is this the plan we should build?"
OPTIONS = ("Aprovar", "Revisar")
SHOWN_IN = "conversation-that-saw-it"


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


def _show(repo: Path, asked: dict, session: str = SHOWN_IN) -> None:
    assert "deny" not in claude_hook(
        repo,
        "ask",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "toolu_1",
            "tool_input": asked,
            "session_id": session,
        },
    )


def _type(repo: Path, text: str, session: str = SHOWN_IN) -> str:
    return claude_hook(repo, "prompt", {"prompt": text, "session_id": session})


def _to_chat(repo: Path) -> None:
    moved = _cli(
        repo, "decision", "fallback", "--host", "claude", "--native-unavailable"
    )
    assert moved.returncode == 0, moved.stderr


def test_the_trials_replies_record_the_first_and_ignore_the_rest(
    tmp_path: Path,
) -> None:
    _show(tmp_path, _present(tmp_path))
    _to_chat(tmp_path)

    first = _type(tmp_path, "1")
    rest = [_type(tmp_path, "Aprovar"), _type(tmp_path, "Aprovar")]

    assert "human decision recorded: Aprovar" in first
    assert decisions.record(tmp_path)["answer"] == "Aprovar"
    assert all("not recorded" not in said and "deny" not in said for said in rest)


def test_a_reply_to_a_dialog_still_on_screen_counts(tmp_path: Path) -> None:
    _show(tmp_path, _present(tmp_path))

    _type(tmp_path, "Revisar")

    assert decisions.record(tmp_path)["answer"] == "Revisar"


def test_the_same_reply_in_another_conversation_answers_nothing(
    tmp_path: Path,
) -> None:
    _show(tmp_path, _present(tmp_path))
    _to_chat(tmp_path)

    _type(tmp_path, "1", session="another-conversation")

    assert decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == ""


def test_a_reply_before_the_question_was_ever_shown_answers_nothing(
    tmp_path: Path,
) -> None:
    _present(tmp_path)

    _type(tmp_path, "1")

    assert decisions.waiting(tmp_path)


def test_showing_it_in_a_second_conversation_lets_that_one_answer(
    tmp_path: Path,
) -> None:
    asked = _present(tmp_path)
    _show(tmp_path, asked)
    _show(tmp_path, asked, session="second-conversation")

    _type(tmp_path, "2", session="second-conversation")

    assert decisions.record(tmp_path)["answer"] == "Revisar"
