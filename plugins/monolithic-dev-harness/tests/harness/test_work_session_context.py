"""Host conversation identity stays at the adapter boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.result import Err, Ok
from harness import work_sessions
from host_adapters import work_session_context

HARNESS = str(Path(__file__).resolve().parents[2] / "bin" / "harness")


def test_an_allowed_switch_binds_the_conversation(tmp_path: Path) -> None:
    session = work_sessions.start(tmp_path, "DAY-001").value
    request = work_session_context.requested(
        f"{HARNESS} work-session select {session.id}", tmp_path, tmp_path
    )
    assert request == (session.id, "select")
    assert work_session_context.bind_requested(
        tmp_path, "codex", "native-session-1", None, request
    ) == Ok(session.id)
    assert work_session_context.resolve_session(
        tmp_path, "codex", "native-session-1"
    ) == Ok(session.id)


def test_only_an_exact_harness_command_asks_for_a_session(tmp_path: Path) -> None:
    for command in (
        "echo harness work-session select WS-12345678",
        f"{HARNESS} work-session select WS-12345678 && touch x",
        f"{HARNESS} work-session select WS-12345678; touch x",
        f"{HARNESS} work-session select $(cat id)",
        "./bin/harness work-session select WS-12345678",
    ):
        assert work_session_context.requested(command, tmp_path, tmp_path) is None, (
            command
        )
    named = f"{HARNESS} workflow checkpoint --label x --session-id WS-12345678"
    assert work_session_context.requested(named, tmp_path, tmp_path) == (
        "WS-12345678",
        "named",
    )


def test_a_named_session_binds_only_an_unbound_conversation(tmp_path: Path) -> None:
    first = work_sessions.start(tmp_path, "DAY-001").value
    second = work_sessions.start(tmp_path, "DAY-002").value
    named = (second.id, "named")
    assert work_session_context.mismatch(first.id, named) is not None
    assert work_session_context.mismatch(None, named) is None
    assert work_session_context.bind_requested(
        tmp_path, "codex", "native-a", first.id, named
    ) == Ok(first.id)
    assert work_session_context.resolve_session(tmp_path, "codex", "native-a") == Ok(
        None
    )


def test_select_needs_an_active_session_and_resume_a_resumable_one(
    tmp_path: Path,
) -> None:
    session = work_sessions.start(tmp_path, "DAY-001").value
    work_sessions.transition(tmp_path, session.id, "pause")
    select = work_session_context.bind_session(
        tmp_path, "codex", "native-a", session.id, "select"
    )
    assert isinstance(select, Err)
    resume = work_session_context.bind_session(
        tmp_path, "codex", "native-a", session.id, "resume"
    )
    assert resume == Ok(session.id)


def test_unknown_host_session_does_not_guess_a_project_work_session(
    tmp_path: Path,
) -> None:
    work_sessions.start(tmp_path, "DAY-001")
    assert work_session_context.resolve_session(
        tmp_path, "codex", "not-yet-bound"
    ) == Ok(None)


def test_corrupt_host_session_link_fails_closed(tmp_path: Path) -> None:
    source = (
        tmp_path
        / work_session_context.ROOT
        / "codex"
        / (hashlib.sha256(b"native-session-2").hexdigest() + ".json")
    )
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"version": 99}), encoding="utf-8")

    assert isinstance(
        work_session_context.resolve_session(tmp_path, "codex", "native-session-2"),
        Err,
    )


def test_a_conversation_with_no_link_acts_in_the_projects_current_session(
    tmp_path: Path,
) -> None:
    assert work_sessions.acting(tmp_path, None) is None
    first = work_sessions.start(tmp_path, "DAY-001").value
    second = work_sessions.start(tmp_path, "DAY-002").value
    assert work_sessions.acting(tmp_path, None) == second.id
    assert work_sessions.acting(tmp_path, first.id) == first.id


def test_a_command_without_a_session_asks_for_the_current_one(tmp_path: Path) -> None:
    session = work_sessions.start(tmp_path, "DAY-001").value
    unnamed = f"{HARNESS} decision present --repo {tmp_path} --gate publish-branch"
    assert work_session_context.requested(unnamed, tmp_path, tmp_path) == (
        session.id,
        "implied",
    )
    elsewhere = f"{HARNESS} decision present --repo {tmp_path / 'other'}"
    assert work_session_context.requested(elsewhere, tmp_path, tmp_path) is None
    assert work_session_context.requested(f"{HARNESS} next", tmp_path, tmp_path) is None


def test_no_current_session_leaves_a_command_without_one_unrequested(
    tmp_path: Path,
) -> None:
    assert (
        work_session_context.requested(
            f"{HARNESS} decision status --repo {tmp_path}", tmp_path, tmp_path
        )
        is None
    )


def test_an_implied_session_must_be_the_one_the_conversation_works_in() -> None:
    implied = ("WS-current", "implied")
    assert work_session_context.mismatch("WS-other", implied) is not None
    assert (
        "--session-id WS-other"
        in work_session_context.mismatch("WS-other", implied).message
    )
    assert work_session_context.mismatch("WS-current", implied) is None
    assert work_session_context.mismatch(None, implied) is None
    assert work_session_context.bind_requested(
        Path("."), "codex", "native-a", None, implied
    ) == Ok(None)
