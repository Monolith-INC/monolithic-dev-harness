"""Changing question delivery never invents an answer or drops its review."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from core.result import Err, Ok
from harness import decisions, state
from host_adapters.codex_runtime import CodexRuntimeProfile, DecisionContext
from host_adapters.interactions import present as host_present
from tests.harness.test_codex_answer_capture import answer, ask, question
from tests.harness.test_decisions import CLI, HOOK, native
from tests.settings_fixture import write_settings


def present(repo: Path, *_available: str) -> dict:
    """Synthetic prepared decision for capture tests; not evidence of CLI availability."""
    assert isinstance(
        decisions.begin(
            repo, "synthetic-review", "Confirm?", ("Yes", "No"), "blocking"
        ),
        Ok,
    )
    return {
        **host_present(
            {
                "id": "synthetic-review",
                "header": "Review",
                "question": "Confirm?",
                "options": [
                    {"label": "Yes", "description": ""},
                    {"label": "No", "description": ""},
                ],
            },
            "codex",
            True,
            codex_profile=CodexRuntimeProfile(
                surface="desktop",
                mode="plan",
                root=True,
                tools=frozenset({"request_user_input"}),
                evidence=("synthetic-test-fixture",),
                qualified_transports=frozenset({"blocking"}),
            ),
            decision=DecisionContext(),
        ),
        "decision_id": "synthetic-review",
    }


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


def test_failed_blocking_control_uses_chat_when_async_is_unqualified(
    tmp_path: Path,
) -> None:
    present(tmp_path, "--blocking-available")
    assert not (tmp_path / ".harness/settings.json").exists()
    match fallback(tmp_path, "--async-available"):
        case subprocess.CompletedProcess(returncode=0, stdout=shown):
            assert json.loads(shown)["transport"] == "chat"
            assert json.loads(shown)["structured_qualified"] is False
        case result:
            assert result.returncode == 0, result.stderr
    assert decisions.record(tmp_path)["transport"] == "chat"
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


def test_fallback_rebinds_pending_answer_to_the_current_codex_chat(
    tmp_path: Path, monkeypatch
) -> None:
    assert isinstance(
        decisions.begin(
            tmp_path,
            "native-recovery",
            "Confirm recovery?",
            ("Yes", "No"),
            "blocking",
            native_session_id="original-root",
        ),
        Ok,
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "recovery-root")

    assert fallback(tmp_path, "--async-available").returncode == 0
    assert decisions.record(tmp_path)["native_session_id"] == "recovery-root"
    assert decisions.record(tmp_path)["answer"] == ""

    native(tmp_path, "prompt", {"session_id": "original-root", "prompt": "Yes"})
    assert decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"session_id": "recovery-root", "prompt": "Yes"})
    assert not decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == "Yes"


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


def test_rejected_native_question_explains_verbatim_recovery(tmp_path: Path) -> None:
    write_settings(tmp_path)
    shown = present(tmp_path, "--blocking-available")
    offered = shown["questions"][0]
    altered = {
        **offered,
        "id": "planning_scope",
        "question": "Does this work belong to an initiative, or is it standalone?",
    }

    denied = native(
        tmp_path,
        "ask",
        {
            "tool_name": "request_user_input",
            "tool_use_id": "altered-call",
            "tool_input": {"questions": [altered]},
        },
    )

    assert "decision-pending" in denied
    assert "exact question" in denied
    assert shown["decision_id"] in denied
    assert f"harness decision fallback --repo {tmp_path}" in denied
    assert "Do not add decision-id or reason flags" in denied
    assert decisions.record(tmp_path)["id"] == shown["decision_id"]
    assert decisions.waiting(tmp_path)

    retried = native(
        tmp_path,
        "ask",
        {
            "tool_name": "request_user_input",
            "tool_use_id": "exact-call",
            "tool_input": {"questions": [offered]},
        },
    )

    assert not retried
    assert decisions.record(tmp_path)["presentation_id"] == shown["decision_id"]


def test_pending_gate_names_supported_fallback_when_agent_adds_unknown_flags(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    shown = present(tmp_path, "--blocking-available")
    command = (
        f"{CLI} decision fallback --repo {tmp_path} --host codex "
        f"--decision-id {shown['decision_id']} --reason retry --async-available"
    )

    denied = native(
        tmp_path,
        "pre-tool",
        {"tool_name": "Bash", "tool_input": {"command": command}},
    )

    assert "decision-pending" in denied
    assert "run this supported fallback command exactly" in denied
    assert (
        f"harness decision fallback --repo {tmp_path} --host codex --async-available"
        in denied
    )
    assert decisions.waiting(tmp_path)


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
    # Synthetic qualified async delivery exercises capture independently of CLI discovery.
    assert isinstance(decisions.fallback(tmp_path, "async"), Ok)
    match host_present(question(True)["questions"][0], "codex", False, True):
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


def claude_hook(repo: Path, event: str, payload: dict) -> str:
    return subprocess.run(
        [sys.executable, str(HOOK), "--host", "claude", "--event", event],
        input=json.dumps({"cwd": str(repo), **payload}),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout


def test_claude_shows_the_prepared_question_without_an_id(tmp_path: Path) -> None:
    write_settings(tmp_path)
    shown = present(tmp_path, "--blocking-available")
    offered = {k: v for k, v in shown["questions"][0].items() if k != "id"}

    assert "decision-pending" in claude_hook(
        tmp_path,
        "ask",
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {"questions": [{**offered, "question": "Approve all?"}]},
        },
    )
    assert "deny" not in claude_hook(
        tmp_path,
        "ask",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "toolu_exact",
            "tool_input": {"questions": [offered]},
        },
    )
    assert decisions.record(tmp_path)["presentation_id"] == shown["decision_id"]


def test_claude_fallback_command_named_by_the_gate_may_run(tmp_path: Path) -> None:
    write_settings(tmp_path)
    present(tmp_path, "--blocking-available")
    command = (
        f"{CLI} decision fallback --repo {tmp_path} --host claude --native-unavailable"
    )

    assert "deny" not in claude_hook(
        tmp_path, "pre-tool", {"tool_name": "Bash", "tool_input": {"command": command}}
    )


def test_claude_free_text_menu_from_the_trial_is_shown_verbatim(tmp_path: Path) -> None:
    write_settings(tmp_path)
    shown = json.loads(
        subprocess.run(
            [
                str(CLI),
                "decision",
                "present",
                "--repo",
                str(tmp_path),
                "--host",
                "claude",
                "--blocking-available",
                "--question",
                "How should the two counts appear on the task screen?",
                "--option",
                "One line",
                "--detail",
                "Example: '2 tasks left · 1 done'.",
                "--option",
                "Two lines",
                "--detail",
                "Stacked.",
                "--recommended",
                "One line",
                "--allow-free-text",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert "deny" not in claude_hook(
        tmp_path,
        "ask",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "toolu_trial",
            "tool_input": {"questions": shown["questions"]},
        },
    )
    assert decisions.record(tmp_path)["presentation_id"] == shown["decision_id"]


def _claude_present(repo: Path, *available: str) -> dict:
    return json.loads(
        subprocess.run(
            [
                str(CLI),
                "decision",
                "present",
                "--repo",
                str(repo),
                "--host",
                "claude",
                *available,
                "--gate",
                "planning-depth",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )


def test_claude_asks_with_its_native_control_unless_told_it_cannot(
    tmp_path: Path,
) -> None:
    """Trial test-012: the agent never passed --blocking-available, so every question was a typed menu."""
    write_settings(tmp_path)
    assert _claude_present(tmp_path)["tool"] == "AskUserQuestion"
    fallback_repo = tmp_path / "fallback"
    fallback_repo.mkdir()
    write_settings(fallback_repo)
    assert _claude_present(fallback_repo, "--native-unavailable")["transport"] == "chat"


def test_claude_code_is_read_as_claude(tmp_path: Path) -> None:
    write_settings(tmp_path)
    assert (
        _claude_present(tmp_path, "--host", "claude-code")["tool"] == "AskUserQuestion"
    )


def test_a_dismissed_claude_question_is_no_answer(tmp_path: Path) -> None:
    """rc.10 trial: "[No preference]" was recorded as the user's own words and acted on."""
    write_settings(tmp_path)
    shown = json.loads(
        subprocess.run(
            [
                str(CLI),
                "decision",
                "present",
                "--repo",
                str(tmp_path),
                "--host",
                "claude",
                "--blocking-available",
                "--question",
                "How should we fix where work items are saved?",
                "--option",
                "Set it up here",
                "--option",
                "Fix the tool",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    asked = {"questions": shown["questions"]}
    claude_hook(
        tmp_path,
        "ask",
        {"tool_name": "AskUserQuestion", "tool_use_id": "toolu_d", "tool_input": asked},
    )
    dismissed = {
        **asked,
        "answers": {shown["questions"][0]["question"]: "[No preference]"},
    }
    note = claude_hook(
        tmp_path,
        "answer",
        {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "toolu_d",
            "tool_input": dismissed,
            "tool_response": dismissed,
        },
    )
    assert "chose no option" in note
    assert decisions.pending(tmp_path) is not None
    assert "decision-pending" in claude_hook(
        tmp_path,
        "pre-tool",
        {"tool_name": "Bash", "tool_input": {"command": "touch notes.txt"}},
    )
