"""Host conversation identity stays at the adapter boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.result import Err, Ok
from harness import work_sessions
from host_adapters import work_session_context
from policy.events import CanonicalToolEvent


def test_adapter_records_and_resolves_native_session_to_project_work(
    tmp_path: Path,
) -> None:
    session = work_sessions.start(tmp_path, "DAY-001").value
    event = CanonicalToolEvent(
        client="codex",
        tool_name="Bash",
        kind="shell",
        workspace_root=str(tmp_path),
        command="harness work-session select " + session.id,
        host_session_id="native-session-1",
    )

    assert work_session_context.for_event(tmp_path, event) == Ok(session.id)
    assert work_session_context.resolve_session(
        tmp_path, "codex", "native-session-1"
    ) == Ok(session.id)


def test_adapter_requires_session_id_for_session_scoped_commands() -> None:
    result = work_session_context._explicit_work_session(
        "harness workflow begin --work-item DAY-001 --session-id WS-12345678"
    )

    assert result == Ok("WS-12345678")


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
