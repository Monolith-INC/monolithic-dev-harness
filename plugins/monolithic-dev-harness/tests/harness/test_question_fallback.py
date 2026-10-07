"""Changing question delivery never invents an answer or drops its review."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from core.result import Err, Ok
from harness import decisions, state
from tests.harness.test_bootstrap_confirmation import present
from tests.harness.test_codex_answer_capture import answer, ask, question
from tests.harness.test_decisions import CLI, native
from tests.settings_fixture import write_settings


def fallback(repo: Path, *available: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(CLI),
            "decision",
            "fallback",
            "--repo",
            str(repo),
            "--host",
            "codex",
            *available,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_failed_blocking_control_falls_back_to_async_then_chat(tmp_path: Path) -> None:
    present(tmp_path, "--blocking-available")
    assert not (tmp_path / ".harness/settings.json").exists()
    match fallback(tmp_path, "--async-available"):
        case subprocess.CompletedProcess(returncode=0, stdout=shown):
            assert json.loads(shown)["tool"] == "request_user_input_async"
        case result:
            assert result.returncode == 0, result.stderr
    assert decisions.record(tmp_path)["transport"] == "async"
    assert decisions.waiting(tmp_path)
    match fallback(tmp_path, "--async-available"):
        case subprocess.CompletedProcess(returncode=0, stdout=shown):
            assert json.loads(shown)["transport"] == "chat"
        case result:
            assert result.returncode == 0, result.stderr
    assert decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"prompt": "Yes"})
    assert decisions.record(tmp_path)["answer"] == "Yes"
    assert state.active_approval(tmp_path) is None


def test_chat_fallback_preserves_checked_approval_and_prevents_replay(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    ask(tmp_path, True)
    assert fallback(tmp_path).returncode == 0
    assert decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is None
    native(tmp_path, "prompt", {"prompt": "Approve"})
    assert not decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is not None
    state.revoke_approvals(tmp_path)
    answer(tmp_path, '{"answers":{"approval":{"answers":["Approve"]}}}', True)
    assert state.active_approval(tmp_path) is None


def test_fallback_cannot_replace_or_answer_the_question(tmp_path: Path) -> None:
    assert isinstance(
        decisions.begin(tmp_path, "review", "Confirm?", ("Yes", "No"), "blocking"), Ok
    )
    assert fallback(tmp_path, "--question", "Approve everything?").returncode != 0
    assert decisions.record(tmp_path)["question"] == "Confirm?"
    assert decisions.waiting(tmp_path)
    assert isinstance(decisions.fallback(tmp_path, "blocking"), Err)


def test_fallback_command_is_allowed_while_waiting_but_cannot_carry_a_write(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    present(tmp_path, "--blocking-available")
    assert "deny" not in native(
        tmp_path,
        "pre-tool",
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": f"{CLI} decision fallback --repo {tmp_path} --host codex --async-available"
            },
        },
    )
    assert "decision-pending" in native(
        tmp_path,
        "pre-tool",
        {
            "tool_name": "Bash",
            "tool_input": {"command": f"{CLI} decision fallback; touch escaped"},
        },
    )


def transcript(repo: Path, session: str, *, approval: bool = False) -> Path:
    (repo / "host-transcript.jsonl").write_text(
        "\n".join(
            map(
                json.dumps,
                (
                    {
                        "type": "session_meta",
                        "payload": {"id": session, "cwd": str(repo)},
                    },
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "request_user_input",
                            "call_id": "captured-call",
                            "arguments": json.dumps(question(approval)),
                        },
                    },
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "captured-call",
                            "output": json.dumps(
                                {
                                    "answers": {
                                        question(approval)["questions"][0]["id"]: {
                                            "answers": [
                                                {
                                                    True: "Approve",
                                                    False: "Start feature work (Recommended)",
                                                }[approval]
                                            ]
                                        },
                                    }
                                }
                            ),
                        },
                    },
                ),
            )
        )
    )
    return repo / "host-transcript.jsonl"


def test_next_real_prompt_recovers_a_previously_captured_answer(tmp_path: Path) -> None:
    write_settings(tmp_path)
    ask(tmp_path)
    native(
        tmp_path,
        "prompt",
        {
            "prompt": "backlog/DAY-003-shared-lists.md",
            "session_id": "original-chat",
            "transcript_path": str(transcript(tmp_path, "original-chat")),
        },
    )
    assert not decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == "Start feature work (Recommended)"
    assert state.active_approval(tmp_path) is None


def test_transcript_from_a_different_chat_cannot_recover_the_answer(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    ask(tmp_path, approval=True)
    native(
        tmp_path,
        "prompt",
        {
            "prompt": "ordinary message",
            "session_id": "original-chat",
            "transcript_path": str(transcript(tmp_path, "another-chat", approval=True)),
        },
    )
    assert decisions.waiting(tmp_path)


def test_recovery_still_honors_the_current_revocation(tmp_path: Path) -> None:
    write_settings(tmp_path)
    ask(tmp_path, True)
    native(
        tmp_path,
        "prompt",
        {
            "prompt": "harness revoke",
            "session_id": "original-chat",
            "transcript_path": str(
                transcript(tmp_path, "original-chat", approval=True)
            ),
        },
    )
    assert not decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is None


def test_route_fallback_accepts_the_actual_chat_request(tmp_path: Path) -> None:
    write_settings(tmp_path)
    ask(tmp_path)
    assert fallback(tmp_path).returncode == 0
    native(tmp_path, "prompt", {"prompt": "harness revoke"})
    assert decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"prompt": "backlog/DAY-003-shared-lists.md"})
    assert decisions.record(tmp_path)["answer"] == "backlog/DAY-003-shared-lists.md"
    assert state.active_approval(tmp_path) is None


def test_fallback_preserves_stale_review_protection(tmp_path: Path) -> None:
    (tmp_path / "review.md").write_text("original review")
    assert isinstance(
        decisions.begin(
            tmp_path,
            "review",
            "Approve?",
            ("Approve", "Revise"),
            "blocking",
            (
                (
                    "review.md",
                    hashlib.sha256((tmp_path / "review.md").read_bytes()).hexdigest(),
                ),
            ),
            approval=True,
        ),
        Ok,
    )
    assert fallback(tmp_path).returncode == 0
    (tmp_path / "review.md").write_text("different review")
    native(tmp_path, "prompt", {"prompt": "Approve"})
    assert decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is None
    native(tmp_path, "prompt", {"prompt": "Revise"})
    assert not decisions.waiting(tmp_path)


def test_alternative_buttons_capture_and_consume_the_new_call_only(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    ask(tmp_path, True)
    match json.loads(fallback(tmp_path, "--async-available").stdout):
        case {"questions": [offered]}:
            native(
                tmp_path,
                "ask",
                {
                    "tool_name": "request_user_input_async",
                    "tool_use_id": "alternative-call",
                    "tool_input": {"questions": [offered]},
                },
            )
            native(
                tmp_path,
                "prompt",
                {
                    "prompt": "<send_user_message_question_reply>"
                    + json.dumps(
                        [
                            {
                                "questionItemId": json.dumps(
                                    ["request_user_input_async", "alternative-call", 0]
                                ),
                                "question": offered["title"],
                                "answer": "Approve",
                            }
                        ]
                    )
                    + "</send_user_message_question_reply>"
                },
            )
            assert not decisions.waiting(tmp_path)
            assert state.active_approval(tmp_path) is not None
            state.revoke_approvals(tmp_path)
            answer(tmp_path, '{"answers":{"approval":{"answers":["Approve"]}}}', True)
            assert state.active_approval(tmp_path) is None
        case _:
            raise AssertionError("fallback did not offer the same question")
