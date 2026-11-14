"""Every hook event stops inside its own time limit and says what to do next, never going quiet.

The limit is counted from the moment the hook process started. A timeout records nothing, and
the way out it names changes with each repeat, so the agent is never sent round the same loop.
Once an answer starts being recorded it is finished, so a timeout never loses half of one.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import time
import types
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, hook, hook_budget, questions, state
from tests.harness.test_codex_answer_capture import question
from tests.settings_fixture import write_settings

SLOW = 3.0
BUDGET = 0.5


def _run(
    repo: Path, event: str, payload: dict, host: str = "codex"
) -> tuple[str, float]:
    """One hook event in this process, so a step can be made slow; its output and duration."""
    out = io.StringIO()
    started = time.monotonic()
    with (
        pytest.MonkeyPatch.context() as patch,
        contextlib.redirect_stdout(out),
    ):
        patch.setattr(
            sys, "stdin", io.StringIO(json.dumps({"cwd": str(repo), **payload}))
        )
        assert hook.main(["--host", host, "--event", event]) == 0
    return out.getvalue(), time.monotonic() - started


@pytest.fixture
def tight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hook_budget, "OTHER_SECONDS", BUDGET)
    monkeypatch.setattr(hook_budget, "PRE_TOOL_SECONDS", BUDGET)


@pytest.fixture
def slow(monkeypatch: pytest.MonkeyPatch, tight: None) -> None:
    """A step every event takes stalls well past the budget."""

    def stall(*_args, **_kwargs):
        time.sleep(SLOW)
        return Ok((False, None))

    monkeypatch.setattr(hook.process_channel, "event", stall)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write_settings(tmp_path)
    assert isinstance(
        decisions.begin(tmp_path, "d1", "Continue?", ("Continue", "Stop"), "chat"), Ok
    )
    return tmp_path


def _asked(tool_use_id: str = "captured-call", approval: bool = True) -> dict:
    return {
        "tool_name": "request_user_input",
        "tool_use_id": tool_use_id,
        "tool_input": question(approval),
    }


@pytest.mark.parametrize("event", ["ask", "answer", "prompt", "stop", "pre-tool"])
def test_each_event_with_a_slow_step_returns_inside_its_budget(
    repo: Path, slow: None, event: str
) -> None:
    payload = {
        "ask": _asked(),
        "answer": {**_asked(), "tool_response": "Approve"},
        "prompt": {"prompt": "Continue"},
        "stop": {"last_assistant_message": "Done."},
        "pre-tool": {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "app.py"), "content": "x = 1\n"},
        },
    }[event]

    _, took = _run(repo, event, payload)

    assert took < BUDGET + 1.0
    assert decisions.waiting(repo)  # nothing was recorded


def test_a_question_that_runs_out_of_time_is_sent_back_to_be_shown_again(
    repo: Path, slow: None
) -> None:
    shown, _ = _run(repo, "ask", _asked())

    assert "[harness hook-budget]" in shown and "deny" in shown
    assert "Show the same question again" in shown


def test_an_answer_that_runs_out_of_time_says_it_was_not_recorded(
    repo: Path, slow: None
) -> None:
    said, _ = _run(repo, "prompt", {"prompt": "Continue"})

    assert "did not record this answer" in said
    assert "Show the same question again" in said
    assert decisions.waiting(repo)


def test_a_stop_that_runs_out_of_time_lets_the_turn_end(repo: Path, slow: None) -> None:
    said, _ = _run(repo, "stop", {"last_assistant_message": "Done."})

    assert said == ""


def test_a_tool_call_that_runs_out_of_time_blocks_writes_but_not_reads(
    repo: Path, slow: None
) -> None:
    write, _ = _run(
        repo,
        "pre-tool",
        {"tool_name": "Write", "tool_input": {"file_path": str(repo / "a.py")}},
        host="claude",
    )
    read, _ = _run(
        repo,
        "pre-tool",
        {"tool_name": "Read", "tool_input": {"file_path": str(repo / "a.py")}},
        host="claude",
    )

    assert "harness-error" in write and "ran out of time" in write
    assert "deny" not in read


def test_each_repeat_names_a_different_way_out(repo: Path, slow: None) -> None:
    said = [_run(repo, "prompt", {"prompt": "Continue"})[0] for _ in range(3)]

    assert "Show the same question again" in said[0]
    assert "type the number of their choice" in said[1]
    assert "harness suspend" in said[2]
    assert len(set(said)) == 3


def test_a_timeout_long_after_the_last_one_starts_again_gently(
    repo: Path, slow: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run(repo, "prompt", {"prompt": "Continue"})
    _run(repo, "prompt", {"prompt": "Continue"})
    monkeypatch.setattr(hook_budget, "REPEAT_WINDOW_SECONDS", 0)

    said, _ = _run(repo, "prompt", {"prompt": "Continue"})

    assert "Show the same question again" in said


def test_the_budget_counts_from_the_start_of_the_process(
    repo: Path, tight: None
) -> None:
    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(out):
        patch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps({"cwd": str(repo), "prompt": "Continue"})),
        )
        hook.main(
            ["--host", "codex", "--event", "prompt"],
            started=time.monotonic() - BUDGET,
        )

    assert "did not record this answer" in out.getvalue()
    assert decisions.waiting(repo)


def test_without_an_alarm_the_clock_is_checked_between_steps(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tight: None
) -> None:
    monkeypatch.setattr(hook_budget, "signal", types.SimpleNamespace())

    def stall(*_args, **_kwargs):
        time.sleep(BUDGET + 0.2)
        return Ok((False, None))

    monkeypatch.setattr(hook.process_channel, "event", stall)

    said, _ = _run(repo, "prompt", {"prompt": "Continue"})

    assert "did not record this answer" in said
    assert decisions.waiting(repo)


def test_a_timeout_between_the_record_and_the_marker_loses_nothing(
    tmp_path: Path, tight: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_settings(tmp_path)
    _run(tmp_path, "ask", _asked())
    assert decisions.waiting(tmp_path)
    marker = hook._apply_marker

    def late(*args, **kwargs):
        time.sleep(BUDGET + 0.3)  # the budget runs out after the answer was recorded
        return marker(*args, **kwargs)

    monkeypatch.setattr(hook, "_apply_marker", late)

    said, _ = _run(
        tmp_path,
        "answer",
        {
            **_asked(),
            "tool_response": '{"answers":{"approval":{"answers":["Approve"]}}}',
        },
    )

    assert "hook-budget" not in said
    assert not decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == "Approve"
    assert state.active_approval(tmp_path) is not None


@pytest.mark.parametrize("previously_shown", [False, True])
def test_a_timed_out_showing_preserves_the_previous_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previously_shown: bool
) -> None:
    write_settings(tmp_path)
    asked = {
        "questions": [
            {
                "header": "Plan",
                "question": "Approve this plan?",
                "multiSelect": False,
                "options": [
                    {"label": "Approve", "description": "Proceed."},
                    {"label": "Revise", "description": "Change."},
                ],
            }
        ]
    }
    payload = {"tool_name": "AskUserQuestion", "tool_input": asked, "session_id": "s1"}
    if previously_shown:
        shown, _ = _run(
            tmp_path, "ask", {**payload, "tool_use_id": "visible"}, "claude"
        )
        assert "deny" not in shown
    before = decisions.record(tmp_path)
    original = state.mark_asked

    def slow_mark(*args, **kwargs):
        original(*args, **kwargs)
        time.sleep(SLOW)

    with monkeypatch.context() as patch:
        patch.setattr(hook_budget, "OTHER_SECONDS", BUDGET)
        patch.setattr(state, "mark_asked", slow_mark)
        denied, _ = _run(
            tmp_path, "ask", {**payload, "tool_use_id": "unseen"}, "claude"
        )
    assert "hook-budget" in denied and "deny" in denied
    assert decisions.record(tmp_path) == before
    assert state.take_asked(tmp_path, questions.marker_name("unseen")) is None
    if previously_shown:
        response = {**asked, "answers": {"Approve this plan?": "Approve"}}
        _run(
            tmp_path,
            "answer",
            {
                **payload,
                "tool_use_id": "visible",
                "tool_input": response,
                "tool_response": response,
            },
            "claude",
        )
        assert decisions.record(tmp_path)["answer"] == "Approve"
    else:
        _run(tmp_path, "prompt", {"prompt": "1", "session_id": "s1"}, "claude")
        assert decisions.record(tmp_path) is None
