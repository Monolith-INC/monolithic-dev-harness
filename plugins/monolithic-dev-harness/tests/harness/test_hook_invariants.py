"""Two promises every question hook keeps, whatever decision is waiting.

Rule 1: the question, answer, prompt and stop hooks never reach the tracker. A tracker can be slow
or down, and these hooks run against the host's 10 seconds. (The check before a tool call still
reads it; that is a later slice.)

Rule 4: while a decision waits, showing it again and answering it, by button or by typing in the
conversation that saw it, are never refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions
from integrations import gateway_client, registry
from tests.harness.test_hook_budget import _run
from tests.harness.test_plan_receipt import OPTIONS, QUESTION, _pending
from tests.settings_fixture import write_settings

SESSION = "conversation-that-saw-it"


def _question(question: str = QUESTION, options: tuple[str, ...] = OPTIONS) -> dict:
    return {
        "questions": [
            {
                "header": "Plan",
                "question": question,
                "multiSelect": False,
                "options": [
                    {"label": option, "description": f"{option}."} for option in options
                ],
            }
        ]
    }


def _ask(repo: Path, asked: dict, call: str = "toolu_1") -> str:
    return _run(
        repo,
        "ask",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": call,
            "tool_input": asked,
            "session_id": SESSION,
        },
        host="claude",
    )[0]


def _click(repo: Path, asked: dict, label: str, call: str = "toolu_1") -> str:
    first = asked["questions"][0]["question"]
    answered = {**asked, "answers": {first: label}}
    return _run(
        repo,
        "answer",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": call,
            "tool_input": answered,
            "tool_response": answered,
            "session_id": SESSION,
        },
        host="claude",
    )[0]


def _type(repo: Path, text: str) -> str:
    return _run(repo, "prompt", {"prompt": text, "session_id": SESSION}, host="claude")[
        0
    ]


def _cut_tracker(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """From now on, every attempt to reach the tracker, which fails as if it were down."""
    calls: list[str] = []

    def reached(*_args, **_kwargs):
        calls.append("tracker")
        raise ConnectionError("the tracker is down")

    monkeypatch.setattr(registry, "_transport", reached)
    monkeypatch.setattr(gateway_client, "open_selected", reached)
    return calls


def _scoped(repo: Path) -> str:
    _, scope, _ = _pending(repo)
    return scope


def test_showing_and_clicking_never_reach_the_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = _scoped(tmp_path)
    tracker_calls = _cut_tracker(monkeypatch)
    asked = _question()

    assert "deny" not in _ask(tmp_path, asked)
    _click(tmp_path, asked, "Approve")

    assert tracker_calls == []
    assert (decisions.record(tmp_path, scope) or {})["answer"] == "Approve"


def test_typing_an_answer_never_reaches_the_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = _scoped(tmp_path)
    tracker_calls = _cut_tracker(monkeypatch)

    _type(tmp_path, "Approve")

    assert tracker_calls == []
    assert (decisions.record(tmp_path, scope) or {})["answer"] == "Approve"


def test_ending_a_turn_never_reaches_the_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scoped(tmp_path)
    tracker_calls = _cut_tracker(monkeypatch)

    _run(tmp_path, "stop", {"last_assistant_message": "Here is the plan."}, "claude")

    assert tracker_calls == []


def _chat(repo: Path) -> str | None:
    write_settings(repo)
    decisions.begin(repo, "d1", QUESTION, OPTIONS, "chat")
    return None


def _dialog(repo: Path) -> str | None:
    write_settings(repo)
    decisions.begin(repo, "d1", QUESTION, OPTIONS, "blocking")
    return None


def _moved_to_chat(repo: Path) -> str | None:
    _dialog(repo)
    assert isinstance(decisions.fallback(repo, "chat"), Ok)
    return None


WAITING = {
    "in the chat": _chat,
    "for a dialog": _dialog,
    "moved to the chat": _moved_to_chat,
    "a plan approval": _scoped,
}


@pytest.mark.parametrize("waiting", list(WAITING))
def test_a_waiting_decision_can_always_be_shown_again_and_clicked(
    tmp_path: Path, waiting: str
) -> None:
    scope = WAITING[waiting](tmp_path)
    asked = _question()

    for call in ("toolu_1", "toolu_2"):
        assert "deny" not in _ask(tmp_path, asked, call)
    _click(tmp_path, asked, OPTIONS[1], call="toolu_2")

    assert (decisions.record(tmp_path, scope) or {})["answer"] == OPTIONS[1]


@pytest.mark.parametrize("waiting", list(WAITING))
def test_a_waiting_decision_shown_here_can_always_be_typed(
    tmp_path: Path, waiting: str
) -> None:
    scope = WAITING[waiting](tmp_path)
    assert "deny" not in _ask(tmp_path, _question())

    _type(tmp_path, "2")

    assert (decisions.record(tmp_path, scope) or {})["answer"] == OPTIONS[1]
