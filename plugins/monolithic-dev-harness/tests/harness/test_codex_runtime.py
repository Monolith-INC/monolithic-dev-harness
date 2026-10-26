"""Codex question delivery follows observed mode and never grants authority."""

import json
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import decisions, state
from host_adapters.codex_runtime import (
    CodexRuntimeProfile,
    DecisionContext,
    load_profile,
    observed_profile,
    persist_observation,
    select_question_transport,
)
from host_adapters.interactions import present
from tests.harness.test_decisions import CLI


def profile(**changes: object) -> CodexRuntimeProfile:
    return replace(
        CodexRuntimeProfile(
            surface="desktop",
            mode="plan",
            root=True,
            tools=frozenset({"request_user_input"}),
            evidence=("native-test-observation",),
            qualified_transports=frozenset({"blocking"}),
            domain_approval_permitted=True,
        ),
        **changes,
    )


def test_profiles_and_context_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        profile().mode = "default"
    with pytest.raises(FrozenInstanceError):
        DecisionContext().kind = "preference"


@pytest.mark.parametrize("kind", ["required", "approval"])
def test_permitted_qualified_plan_domain_decision(kind: str) -> None:
    assert select_question_transport(profile(), DecisionContext(kind=kind)) == Ok(
        "blocking"
    )


def test_plan_approval_needs_explicit_permission_and_observed_surface() -> None:
    assert isinstance(
        select_question_transport(
            profile(domain_approval_permitted=False), DecisionContext(kind="approval")
        ),
        Err,
    )
    assert isinstance(
        select_question_transport(
            profile(qualified_transports=frozenset()), DecisionContext()
        ),
        Err,
    )


def test_default_optional_question_never_claims_blocking() -> None:
    assert select_question_transport(
        profile(mode="default", default_question_enabled=True),
        DecisionContext(kind="preference"),
    ) == Ok("blocking")
    assert (
        present(
            {"id": "language", "question": "Choose?", "options": []},
            "codex",
            True,
            codex_profile=profile(mode="default", default_question_enabled=True),
            decision=DecisionContext(kind="preference"),
        )["isBlocking"]
        is False
    )


@pytest.mark.parametrize("kind", ["required", "approval"])
def test_default_cannot_turn_required_decision_into_optional(kind: str) -> None:
    assert isinstance(
        select_question_transport(
            profile(mode="default", default_question_enabled=True),
            DecisionContext(kind=kind),
        ),
        Err,
    )
    assert isinstance(
        select_question_transport(
            profile(mode="default", default_question_enabled=True),
            DecisionContext(kind="preference", approval=True),
        ),
        Err,
    )


def test_unavailable_default_question_and_unknown_profile_use_chat_only_if_allowed() -> (
    None
):
    assert select_question_transport(
        profile(mode="default"), DecisionContext(kind="preference")
    ) == Ok("chat")
    assert select_question_transport(
        CodexRuntimeProfile(), DecisionContext(kind="preference")
    ) == Ok("chat")
    assert select_question_transport(
        CodexRuntimeProfile(), DecisionContext(structured_required=False)
    ) == Ok("chat")
    match select_question_transport(CodexRuntimeProfile(), DecisionContext()):
        case Err(failure):
            assert failure.code == "unsupported_decision_transport"
        case other:
            pytest.fail(str(other))


def test_child_cannot_ask_root_human_or_use_async() -> None:
    assert isinstance(
        select_question_transport(profile(root=False), DecisionContext()), Err
    )
    assert isinstance(
        select_question_transport(
            profile(root=False), DecisionContext(kind="preference")
        ),
        Err,
    )


def test_async_requires_advertised_root_tool_and_independent_permission() -> None:
    assert select_question_transport(
        profile(
            mode="default",
            tools=frozenset({"request_user_input_async", "clock.sleep"}),
            qualified_transports=frozenset({"async"}),
            async_required_permitted=True,
        ),
        DecisionContext(),
    ) == Ok("async")
    assert isinstance(
        select_question_transport(
            profile(
                mode="default",
                tools=frozenset({"request_user_input_async", "clock.sleep"}),
                qualified_transports=frozenset({"async"}),
            ),
            DecisionContext(),
        ),
        Err,
    )
    assert select_question_transport(
        profile(
            mode="unknown",
            tools=frozenset({"request_user_input_async"}),
            qualified_transports=frozenset(),
            async_required_permitted=True,
        ),
        DecisionContext(),
    ) == Ok("async")
    assert (
        present(
            {"id": "review", "question": "Confirm?", "options": []},
            "codex",
            False,
            codex_profile=profile(
                tools=frozenset({"request_user_input_async"}),
                async_required_permitted=True,
            ),
        )["wait"]
        is None
    )


@pytest.mark.parametrize("purpose", ["host_permission", "sandbox_escalation"])
def test_host_permission_never_uses_question_tool(purpose: str) -> None:
    assert isinstance(
        select_question_transport(profile(), DecisionContext(purpose=purpose)), Err
    )


def test_caller_availability_flags_cannot_override_observed_profile() -> None:
    assert (
        present(
            {"id": "approval", "question": "Approve?", "options": []},
            "codex",
            True,
            True,
            codex_profile=CodexRuntimeProfile(),
            decision=DecisionContext(kind="approval"),
        )["transport_error"]["code"]
        == "unsupported_decision_transport"
    )


def test_hook_permission_mode_does_not_establish_collaboration_mode() -> None:
    match observed_profile({"session_id": "root", "permission_mode": "plan"}):
        case Ok(profile):
            assert profile.mode == "unknown"
            assert not profile.qualified_transports
        case other:
            pytest.fail(str(other))


def test_protected_profile_matches_session_and_invalidates_stale_mode(
    tmp_path: Path,
) -> None:
    assert isinstance(
        persist_observation(
            tmp_path,
            {
                "session_id": "root",
                "permission_mode": "plan",
                "tool_name": "request_user_input",
            },
        ),
        Ok,
    )
    assert load_profile(tmp_path, "root").root
    assert load_profile(tmp_path, "other") == CodexRuntimeProfile()
    assert isinstance(
        persist_observation(tmp_path, {"session_id": "root", "agent_type": "worker"}),
        Err,
    )
    assert load_profile(tmp_path, "root").root
    assert isinstance(persist_observation(tmp_path, {"session_id": "root"}), Ok)
    assert not load_profile(tmp_path, "root").tools


def test_cli_unknown_native_mode_keeps_required_decision_pending(
    tmp_path: Path,
) -> None:
    match subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(tmp_path),
            "--host",
            "codex",
            "--blocking-available",
            "--question",
            "Confirm?",
            "--option",
            "Yes",
            "--option",
            "No",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    ):
        case subprocess.CompletedProcess(returncode=0, stdout=message):
            assert (
                json.loads(message)["transport_error"]["code"]
                == "unsupported_decision_transport"
            )
            assert (
                json.loads(message)["native_candidate"]["tool"]
                == "request_user_input_async"
            )
            assert json.loads(message)["state"] == "waiting_for_human"
        case other:
            pytest.fail(str(other))
    assert decisions.waiting(tmp_path)


def test_first_native_async_discovery_binds_exact_pending_and_captures_answer(
    tmp_path: Path, monkeypatch
) -> None:
    from tests.harness.test_decisions import native

    monkeypatch.setenv("CODEX_THREAD_ID", "native-root")
    assert (
        subprocess.run(
            [
                str(CLI),
                "decision",
                "present",
                "--repo",
                str(tmp_path),
                "--host",
                "codex",
                "--question",
                "Confirm?",
                "--option",
                "Yes",
                "--option",
                "No",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )
    assert "deny" not in native(
        tmp_path,
        "ask",
        {
            "session_id": "native-root",
            "turn_id": "turn",
            "model": "model",
            "tool_name": "request_user_input_async",
            "tool_use_id": "actual-call",
            "tool_input": {
                "questions": [{"title": "Confirm?", "options": ["Yes", "No"]}]
            },
        },
    )
    assert decisions.record(tmp_path)["transport"] == "async"
    assert decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is None
    native(tmp_path, "prompt", {"session_id": "native-root", "prompt": "Yes"})
    assert decisions.record(tmp_path)["answer"] == "Yes"


@pytest.mark.parametrize(
    "changed",
    [
        {"session_id": "another-root"},
        {"agent_id": "child"},
        {
            "tool_input": {
                "questions": [{"title": "Different?", "options": ["Yes", "No"]}]
            }
        },
        {
            "tool_input": {
                "questions": [{"title": "Confirm?", "options": ["Approve", "No"]}]
            }
        },
    ],
)
def test_native_async_discovery_rejects_other_identity_or_question(
    tmp_path: Path, monkeypatch, changed: dict
) -> None:
    from tests.harness.test_decisions import native

    monkeypatch.setenv("CODEX_THREAD_ID", "native-root")
    subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(tmp_path),
            "--host",
            "codex",
            "--question",
            "Confirm?",
            "--option",
            "Yes",
            "--option",
            "No",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "deny" in native(
        tmp_path,
        "ask",
        {
            "session_id": "native-root",
            "turn_id": "turn",
            "model": "model",
            "tool_name": "request_user_input_async",
            "tool_use_id": "actual-call",
            "tool_input": {
                "questions": [{"title": "Confirm?", "options": ["Yes", "No"]}]
            },
            **changed,
        },
    )
    assert decisions.record(tmp_path)["transport"] == "chat"
    assert decisions.waiting(tmp_path)
    assert state.active_approval(tmp_path) is None

    assert state.active_approval(tmp_path) is None
    match subprocess.run(
        [str(CLI), "decision", "fallback", "--repo", str(tmp_path), "--host", "codex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    ):
        case subprocess.CompletedProcess(returncode=0, stdout=message):
            assert json.loads(message)["transport"] == "chat"
            assert json.loads(message)["structured_qualified"] is False
        case other:
            pytest.fail(str(other))
    assert decisions.waiting(tmp_path)


@pytest.mark.parametrize(
    "changed",
    [
        {"session_id": "other"},
        {"turn_id": "next"},
        {"model": "other"},
    ],
)
def test_async_observation_expires_with_session_turn_or_model(
    tmp_path: Path, changed: dict[str, str]
) -> None:
    assert isinstance(
        persist_observation(
            tmp_path,
            {
                "session_id": "root",
                "turn_id": "turn",
                "model": "model",
                "tool_name": "request_user_input_async",
                "hook_event_name": "PreToolUse",
            },
        ),
        Ok,
    )
    assert load_profile(tmp_path, "root").async_required_permitted
    assert not load_profile(tmp_path, "root").qualified_transports
    assert isinstance(
        persist_observation(
            tmp_path,
            {
                "session_id": "root",
                "turn_id": "turn",
                "model": "model",
                "tool_name": "Bash",
            },
        ),
        Ok,
    )
    assert load_profile(tmp_path, "root").async_required_permitted
    assert isinstance(
        persist_observation(
            tmp_path,
            {
                "session_id": "root",
                "turn_id": "turn",
                "model": "model",
                "tool_name": "Bash",
                **changed,
            },
        ),
        Ok,
    )
    assert not load_profile(tmp_path, "root").async_required_permitted


def test_passive_optout_hook_does_not_create_profile(tmp_path: Path) -> None:
    from tests.harness.test_decisions import native

    assert "deny" not in native(
        tmp_path,
        "pre-tool",
        {
            "session_id": "root",
            "turn_id": "turn",
            "model": "model",
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
        },
    )
    assert not (tmp_path / ".harness/state/host_sessions/codex/runtime.json").exists()


def test_cli_optional_language_can_use_chat_without_native_mode(tmp_path: Path) -> None:
    match subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(tmp_path),
            "--host",
            "codex",
            "--gate",
            "language",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    ):
        case subprocess.CompletedProcess(returncode=0, stdout=message):
            assert json.loads(message)["transport"] == "chat"
            assert not decisions.waiting(tmp_path)
        case other:
            pytest.fail(str(other))


def test_discovered_async_answer_from_other_root_cannot_resolve_pending(
    tmp_path: Path,
) -> None:
    from tests.harness.test_decisions import native

    assert isinstance(
        decisions.begin(
            tmp_path,
            "decision-root",
            "Confirm?",
            ("Yes", "No"),
            "chat",
            native_session_id="native-root",
        ),
        Ok,
    )
    native(
        tmp_path,
        "ask",
        {
            "session_id": "native-root",
            "turn_id": "turn",
            "model": "model",
            "tool_name": "request_user_input_async",
            "tool_use_id": "actual-call",
            "tool_input": {
                "questions": [{"title": "Confirm?", "options": ["Yes", "No"]}]
            },
        },
    )
    assert decisions.record(tmp_path)["transport"] == "async"
    native(tmp_path, "prompt", {"session_id": "another-root", "prompt": "Yes"})
    assert decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == ""
