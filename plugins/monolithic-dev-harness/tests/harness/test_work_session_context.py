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
        f"{HARNESS} work-session select {session.id}", tmp_path
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
        assert work_session_context.requested(command, tmp_path) is None, command
    named = f"{HARNESS} workflow checkpoint --label x --session-id WS-12345678"
    assert work_session_context.requested(named, tmp_path) == ("WS-12345678", "named")


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
