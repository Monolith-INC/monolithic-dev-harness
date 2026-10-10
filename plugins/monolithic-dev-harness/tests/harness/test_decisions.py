"""Delayed decisions cannot unlock writes, stale reviews, or another question."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from core.result import Err, Ok
from harness import decisions, review_decisions, state, work_sessions, workflow
from host_adapters import work_session_context
from integrations import gateway
from tests.settings_fixture import write_settings

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / "scripts/harness/hook.py"
CLI = PLUGIN / "bin/harness"


def native(repo: Path, event: str, payload: dict) -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK), "--host", "codex", "--event", event],
        input=json.dumps({"cwd": str(repo), **payload}),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return result.stdout


def test_chat_wait_survives_restart_and_intervening_messages(tmp_path: Path) -> None:
    assert isinstance(
        decisions.begin(tmp_path, "d1", "Continue?", ("Continue", "Stop"), "chat"), Ok
    )
    denied = native(
        tmp_path,
        "pre-tool",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "app.py"), "content": "x=1"},
        },
    )
    assert "Wait for the human" in denied
    native(tmp_path, "prompt", {"prompt": "What is happening?"})
    assert decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"prompt": "continue"})
    assert not decisions.waiting(tmp_path)
    assert (decisions.record(tmp_path) or {})["answer"] == "Continue"
    assert isinstance(decisions.resolve(tmp_path, "d1", "Continue", "chat"), Err)


def test_stale_review_cannot_be_approved_but_can_be_revised(tmp_path: Path) -> None:
    file = tmp_path / "plan.md"
    file.write_text("first")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    decisions.begin(
        tmp_path,
        "d1",
        "Approve?",
        ("Approve", "Revise"),
        "chat",
        (("plan.md", digest),),
        True,
    )
    file.write_text("different")
    native(tmp_path, "prompt", {"prompt": "Approve"})
    assert decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is None
    native(tmp_path, "prompt", {"prompt": "Revise"})
    assert not decisions.waiting(tmp_path)


def test_pending_gate_blocks_workflow_and_gateway_before_configuration(
    tmp_path: Path,
) -> None:
    decisions.begin(tmp_path, "d1", "Continue?", ("Continue",), "chat")
    result = subprocess.run(
        [str(CLI), "workflow", "complete"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0 and "human's answer" in result.stdout + result.stderr
    result = gateway.handle_call(
        "tracker_create_work_item",
        {"kind": "user_story", "title": "t", "description": "d"},
        tmp_path,
    )
    assert isinstance(result, Err)
    assert result.failure.code == "decision_pending"


def test_implementation_confirmation_records_confirmation_stage_and_recovers(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("Reviewed implementation plan\n", encoding="utf-8")
    started = workflow.start("Build the reviewed plan", "en").value
    preparation = workflow.add_point(started, "Bundle prepared", "preparation").value
    assert isinstance(workflow.save(tmp_path, preparation), Ok)

    assert isinstance(
        review_decisions.begin(
            tmp_path,
            "confirm-plan",
            "Approve this implementation plan?",
            ("Approve", "Revise", "Stop here"),
            "chat",
            (("plan.md", workflow.file_digest(plan).value),),
            approval=True,
            gate="implementation-confirm",
        ),
        Ok,
    )

    checkpoint = workflow.load(tmp_path).value
    assert checkpoint.current.stage == "confirmation"
    assert checkpoint.current.artifacts == (
        ("plan.md", workflow.file_digest(plan).value),
    )

    # Re-running recovery is idempotent and retains the truthful stage label.
    assert isinstance(review_decisions.recover(tmp_path), Ok)
    assert workflow.load(tmp_path).value.current.stage == "confirmation"


def test_only_a_plain_status_query_passes_the_pending_gate(tmp_path: Path) -> None:
    write_settings(tmp_path)
    decisions.begin(tmp_path, "d1", "Continue?", ("Continue",), "chat")
    fake = tmp_path / "bin" / "harness"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)

    def shell(command: str) -> str:
        return native(
            tmp_path,
            "pre-tool",
            {"tool_name": "Bash", "tool_input": {"command": command}},
        )

    assert "deny" not in shell(f"{CLI} decision status --repo {tmp_path}")
    for command in (
        "touch notes.txt",
        f"{CLI} decision status; touch P1",
        f'{CLI} decision status --repo "$(touch P2)"',
        f"{CLI} decision status --repo x|touch${{IFS}}P3",
        f"{CLI} decision status --question x",
        "./bin/harness decision status",
    ):
        assert "decision-pending" in shell(command), command
    state.set_harness_mode(tmp_path, "suspended")
    assert "deny" not in shell("touch notes.txt")


def test_second_question_and_wrong_answer_id_cannot_replace_pending(
    tmp_path: Path,
) -> None:
    decisions.begin(tmp_path, "d1", "Continue?", ("Continue",), "chat")
    assert isinstance(
        decisions.begin(tmp_path, "d2", "Another?", ("Yes",), "chat"), Err
    )
    assert isinstance(decisions.resolve(tmp_path, "d2", "Continue", "chat"), Err)
    assert decisions.waiting(tmp_path)


def test_pending_questions_are_isolated_between_project_work_sessions(
    tmp_path: Path,
) -> None:
    first = work_sessions.start(tmp_path, "DAY-001").value
    second = work_sessions.start(tmp_path, "DAY-002").value

    assert isinstance(
        decisions.begin(
            tmp_path,
            "d1",
            "Continue DAY-001?",
            ("Continue", "Stop"),
            "chat",
            work_session_id=first.id,
        ),
        Ok,
    )

    assert decisions.waiting(tmp_path, first.id)
    assert not decisions.waiting(tmp_path, second.id)
    assert not decisions.waiting(tmp_path)
    assert decisions.record(tmp_path, first.id)["question"] == "Continue DAY-001?"
    assert decisions.record(tmp_path, second.id) is None


def test_answer_in_one_work_session_cannot_resolve_another_session_question(
    tmp_path: Path,
) -> None:
    first = work_sessions.start(tmp_path, "DAY-001").value
    second = work_sessions.start(tmp_path, "DAY-002").value
    decisions.begin(
        tmp_path,
        "d1",
        "Continue DAY-001?",
        ("Continue", "Stop"),
        "chat",
        work_session_id=first.id,
    )

    result = decisions.resolve(
        tmp_path, "d1", "Continue", "chat", work_session_id=second.id
    )

    assert isinstance(result, Err)
    assert decisions.waiting(tmp_path, first.id)


def test_a_project_wide_question_is_pending_for_every_session(
    tmp_path: Path,
) -> None:
    session = work_sessions.start(tmp_path, "DAY-001").value
    decisions.begin(tmp_path, "shared", "Continue?", ("Continue",), "chat")

    pending = decisions.pending(tmp_path, session.id)

    assert pending is not None and pending.id == "shared"
    assert pending.scope is None


def test_host_conversations_keep_work_session_questions_separate(
    tmp_path: Path,
) -> None:
    first = work_sessions.start(tmp_path, "DAY-001").value
    second = work_sessions.start(tmp_path, "DAY-002").value
    assert isinstance(
        work_session_context.bind_session(tmp_path, "codex", "native-a", first.id), Ok
    )
    assert isinstance(
        work_session_context.bind_session(tmp_path, "codex", "native-b", second.id), Ok
    )
    assert isinstance(
        decisions.begin(
            tmp_path,
            "decision-a",
            "Continue DAY-001?",
            ("Continue", "Stop"),
            "chat",
            work_session_id=first.id,
        ),
        Ok,
    )

    native(tmp_path, "prompt", {"session_id": "native-b", "prompt": "Continue"})

    assert decisions.waiting(tmp_path, first.id)
    assert not decisions.waiting(tmp_path, second.id)

    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "Continue"})

    assert not decisions.waiting(tmp_path, first.id)
    assert (decisions.record(tmp_path, first.id) or {})["answer"] == "Continue"


def test_scoped_question_refuses_to_start_for_a_paused_work_session(
    tmp_path: Path,
) -> None:
    session = work_sessions.start(tmp_path, "DAY-001").value
    work_sessions.transition(tmp_path, session.id, "pause")

    result = decisions.begin(
        tmp_path,
        "d1",
        "Continue?",
        ("Continue",),
        "chat",
        work_session_id=session.id,
    )

    assert isinstance(result, Err)
    assert not decisions.waiting(tmp_path, session.id)


def test_async_delivery_waits_for_matching_actual_reply(tmp_path: Path) -> None:
    write_settings(tmp_path)
    question = {"questions": [{"title": "Continue?", "options": ["Continue", "Stop"]}]}
    native(
        tmp_path,
        "ask",
        {
            "tool_name": "request_user_input_async",
            "tool_use_id": "call-1",
            "tool_input": question,
        },
    )
    assert decisions.waiting(tmp_path)
    native(
        tmp_path,
        "answer",
        {
            "tool_use_id": "call-1",
            "tool_input": question,
            "tool_response": {"accepted": True},
        },
    )
    assert decisions.waiting(tmp_path)
    denied = native(
        tmp_path,
        "pre-tool",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "app.py"), "content": "x=1"},
        },
    )
    assert "Wait for the human" in denied

    def reply(call: str, answer: str) -> str:
        return (
            "<send_user_message_question_reply>\n"
            + json.dumps(
                [
                    {
                        "questionItemId": json.dumps(
                            ["request_user_input_async", call, 0]
                        ),
                        "question": "Continue?",
                        "answer": answer,
                    }
                ]
            )
            + "\n</send_user_message_question_reply>"
        )

    native(tmp_path, "prompt", {"prompt": reply("wrong-call", "Continue")})
    assert decisions.waiting(tmp_path)
    changed_question = reply("call-1", "Continue").replace(
        '"question": "Continue?"', '"question": "Continue with the next step?"'
    )
    native(tmp_path, "prompt", {"prompt": changed_question})
    assert decisions.waiting(tmp_path)
    for message in (
        "the buttons disappeared",
        "I did not click",
        reply("call-1", "I can reopen it"),
    ):
        native(tmp_path, "prompt", {"prompt": message})
        assert decisions.waiting(tmp_path)
    native(
        tmp_path,
        "answer",
        {
            "tool_use_id": "call-1",
            "tool_input": question,
            "tool_response": {"answers": {"q": {"answers": ["Continue"]}}},
        },
    )
    assert decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"prompt": reply("call-1", "continue")})
    assert not decisions.waiting(tmp_path)
    assert (decisions.record(tmp_path) or {})["answer"] == "Continue"
    native(tmp_path, "prompt", {"prompt": reply("call-1", "Stop")})
    assert (decisions.record(tmp_path) or {})["answer"] == "Continue"


def test_replayed_chat_answer_cannot_change_a_resolved_decision(tmp_path: Path) -> None:
    assert isinstance(
        decisions.begin(tmp_path, "d1", "Continue?", ("Continue", "Stop"), "chat"),
        Ok,
    )

    native(tmp_path, "prompt", {"prompt": "Continue"})
    resolved = decisions.record(tmp_path) or {}
    native(tmp_path, "prompt", {"prompt": "Stop"})

    current = decisions.record(tmp_path) or {}
    assert resolved["status"] == "answered"
    assert current["status"] == "answered"
    assert current["answer"] == "Continue"


def test_blocking_acknowledgment_does_not_resolve_pending(tmp_path: Path) -> None:
    write_settings(tmp_path)
    question = {
        "questions": [
            {
                "id": "q",
                "header": "Review",
                "question": "Continue?",
                "options": [
                    {"label": "Continue", "description": "Move on."},
                    {"label": "Stop", "description": "Stop here."},
                ],
            }
        ]
    }
    native(
        tmp_path,
        "ask",
        {
            "tool_name": "request_user_input",
            "tool_use_id": "q1",
            "tool_input": question,
        },
    )
    assert decisions.waiting(tmp_path)
    native(
        tmp_path,
        "answer",
        {
            "tool_use_id": "q1",
            "tool_input": question,
            "tool_response": {"accepted": True},
        },
    )
    assert decisions.waiting(tmp_path)
    native(
        tmp_path,
        "answer",
        {
            "tool_use_id": "q1",
            "tool_input": question,
            "tool_response": {"answers": {"q": {"answers": ["Continue"]}}},
        },
    )
    assert not decisions.waiting(tmp_path)


def test_prepared_native_question_binds_once(tmp_path: Path) -> None:
    decisions.begin(tmp_path, "prepared", "Continue?", ("Continue", "Stop"), "blocking")
    assert isinstance(
        decisions.bind_question(
            tmp_path, "prepared", "call-1", "Continue?", ("Continue", "Stop")
        ),
        Ok,
    )
    assert isinstance(
        decisions.bind_question(
            tmp_path, "prepared", "call-2", "Continue?", ("Continue", "Stop")
        ),
        Err,
    )
    assert isinstance(
        decisions.resolve(tmp_path, "prepared", "Continue", "blocking"), Err
    )
    assert isinstance(decisions.resolve(tmp_path, "call-1", "Continue", "blocking"), Ok)


def test_invalid_presentation_cannot_create_pending(tmp_path: Path) -> None:
    for options, transport in (
        (("",), "chat"),
        (("A", "B", "C", "D"), "chat"),
        (("A",), "unknown"),
    ):
        assert isinstance(
            decisions.begin(tmp_path, "d1", "Choose?", options, transport), Err
        )
        assert not decisions.waiting(tmp_path)


def test_async_adapter_owns_button_format_and_live_wait() -> None:
    from host_adapters.interactions import present

    shown = present(
        {
            "id": "prepared",
            "question": "Continue?",
            "options": [{"label": "Continue", "description": "Move on"}],
        },
        "codex",
        False,
        True,
    )
    assert shown["tool"] == "request_user_input_async"
    assert shown["questions"] == [{"title": "Continue?", "options": ["Continue"]}]
    assert "keep the turn open" in shown["instruction"]
    assert "ask no follow-up questions" in shown["instruction"]
    assert "Answer question" in shown["instruction"]
    assert shown["wait"] == {"tool": "clock.sleep", "arguments": {"duration_ms": 20000}}
    assert (
        present({"question": "Continue?", "options": []}, "claude", False, True)[
            "transport"
        ]
        == "chat"
    )
