"""Replay of the rc.13 trial lockup (Nov 11, Idea 8256 to Feature 8307), end to end.

What happened: the plan was shown and its approval asked in a dialog. The answer hook was cut off
by the host's 10 seconds, so the approval was never recorded. The agent moved the question to the
chat, every attempt to show it again was refused, and the user's typed "1", "Aprovar", "Aprovar"
changed nothing. The open question then held every tool.

What must happen now, with the tracker down the whole time:
1. the plan approval is prepared and shown in a dialog;
2. the answer hook runs out of time, and the agent is told to show the question again;
3. showing it again is allowed;
4. the user types "Aprovar", and it is recorded;
5. the plan's receipt, written when the question was prepared, is current;
6. the open question no longer holds the next write, and the approval is tied to the plan.

The plan-check hold on a work session's code writes is covered in `test_plan_receipt`; here the
question is prepared project-wide, as `test_plan_receipt` does, so no route step stands in front.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from core.result import Ok
from harness import (
    decisions,
    hook,
    hook_budget,
    plan_review,
    preferences,
    state,
    workflow,
)
from tests.harness.test_hook_budget import _run
from tests.harness.test_hook_invariants import _cut_tracker
from tests.harness.test_plan_receipt import _sourced_plan
from tests.harness.test_plan_review import _cli, _project, _show, _transcript

CONVERSATION = "trial-conversation"


def _prepare(repo: Path) -> tuple[str, str, dict, Path]:
    """The plan, shown and then asked for approval in Portuguese, as in the trial."""
    story = _project(repo)
    assert isinstance(preferences.set_language("pt-br", repo), Ok)
    plan = _sourced_plan(repo, story)
    shown = _show(repo, plan)
    assert shown.returncode == 0, shown.stderr
    asked = _cli(
        repo,
        "decision",
        "present",
        "--host",
        "claude",
        "--blocking-available",
        "--gate",
        "implementation-confirm",
        "--artifact",
        plan,
    )
    assert asked.returncode == 0, asked.stderr
    question = {"questions": json.loads(asked.stdout)["questions"]}
    return story, plan, question, _transcript(repo / "t.jsonl", shown.stdout)


def _ask(repo: Path, question: dict, call: str, transcript: Path) -> str:
    return _run(
        repo,
        "ask",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": call,
            "tool_input": question,
            "session_id": CONVERSATION,
            "transcript_path": str(transcript),
        },
        host="claude",
    )[0]


def test_the_trial_lockup_ends_with_the_approval_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    story, plan, question, transcript = _prepare(tmp_path)
    assert question["questions"][0]["options"][0]["label"] == "Aprovar"
    tracker_calls = _cut_tracker(monkeypatch)

    # 1. Shown in a dialog.
    assert "deny" not in _ask(tmp_path, question, "toolu_a", transcript)

    # 2. The answer hook runs out of time; nothing is recorded, and the way out is named.
    with monkeypatch.context() as slow:
        slow.setattr(hook_budget, "OTHER_SECONDS", 0.5)
        slow.setattr(
            hook.process_channel,
            "event",
            lambda *_a, **_k: (time.sleep(3), Ok((False, None)))[1],
        )
        first = question["questions"][0]["question"]
        answered = {**question, "answers": {first: "Aprovar"}}
        said, took = _run(
            tmp_path,
            "answer",
            {
                "tool_name": "AskUserQuestion",
                "tool_use_id": "toolu_a",
                "tool_input": answered,
                "tool_response": answered,
                "session_id": CONVERSATION,
            },
            host="claude",
        )
    assert took < 2
    assert "did not record this answer" in said
    assert "Show the same question again" in said
    assert decisions.waiting(tmp_path)

    # 3. Showing it again is allowed.
    assert "deny" not in _ask(tmp_path, question, "toolu_b", transcript)

    # 4. The user types their answers, as in the trial: the first is recorded, the rest ignored.
    replies = [
        _run(
            tmp_path,
            "prompt",
            {"prompt": text, "session_id": CONVERSATION},
            host="claude",
        )[0]
        for text in ("Aprovar", "Aprovar")
    ]
    assert "human decision recorded: Aprovar" in replies[0]
    assert "not recorded" not in replies[1]
    assert (decisions.record(tmp_path) or {})["answer"] == "Aprovar"
    assert state.active_approval(tmp_path) is not None

    # 5. The receipt written when the question was prepared matches the plan on disk.
    receipt = plan_review.receipt(tmp_path, story)
    assert receipt["plan"] == plan
    assert receipt["plan_digest"] == workflow.file_digest(tmp_path / plan).value

    # 6. The open question no longer holds the next write; the approval is tied to the plan.
    assert not decisions.blocking(tmp_path, None)
    _, approval = state.active_approval(tmp_path) or (None, {})
    assert plan in json.dumps(approval.get("binds"))
    assert tracker_calls == []
