"""An approval window covers the work session it was opened in, for as long as the settings say."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from core.result import Ok
from harness import decisions, state, work_sessions
from host_adapters import work_session_context
from tests.harness.test_decisions import native
from tests.harness.test_hook_rules import AZ, SETTINGS
from tests.settings_fixture import write_settings

WRITE = {"tool_name": AZ + "wit_work_item_write", "tool_input": {"action": "create"}}


def project(tmp_path: Path, minutes: int = 20) -> tuple[str, str]:
    """A governed project with two work sessions, bound to host conversations a and b."""
    write_settings(
        tmp_path,
        tracker=SETTINGS["tracker"],
        scm=SETTINGS["scm"],
        approvals={"window_minutes": minutes},
    )
    state.set_tracking_mode(tmp_path, "skipped")
    first = work_sessions.start(tmp_path, "DAY-001").value.id
    second = work_sessions.start(tmp_path, "DAY-002").value.id
    for native_id, session in (("native-a", first), ("native-b", second)):
        bound = work_session_context.bind_session(tmp_path, "codex", native_id, session)
        assert isinstance(bound, Ok)
    return first, second


def write(tmp_path: Path, native_id: str | None) -> str:
    session = {"session_id": native_id} if native_id else {}
    return native(tmp_path, "pre-tool", {**WRITE, **session})


def minutes_open(record: dict) -> float:
    opened = datetime.fromisoformat(record["opened"])
    return (datetime.fromisoformat(record["expires"]) - opened) / timedelta(minutes=1)


def test_an_approval_covers_only_its_own_session(tmp_path: Path) -> None:
    project(tmp_path)
    assert "approval-required" in write(tmp_path, "native-a")
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "approve HB-TEST1"})
    assert "deny" not in write(tmp_path, "native-a")
    assert "approval-required" in write(tmp_path, "native-b")
    assert "approval-required" in write(tmp_path, None)


def test_a_project_wide_approval_does_not_cover_a_session(tmp_path: Path) -> None:
    project(tmp_path)
    native(tmp_path, "prompt", {"prompt": "approve HB-TEST1"})
    assert "deny" not in write(tmp_path, None)
    assert "approval-required" in write(tmp_path, "native-a")


def test_writes_are_logged_against_the_session_window(tmp_path: Path) -> None:
    first, _ = project(tmp_path)
    native(tmp_path, "prompt", {"prompt": "approve HB-PROJ1"})
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "approve HB-SESS1"})
    write(tmp_path, "native-a")
    approvals = tmp_path / ".harness" / "state" / "approvals"
    session = json.loads((approvals / "HB-SESS1.json").read_text())
    project_wide = json.loads((approvals / "HB-PROJ1.json").read_text())
    assert session["work_session"] == first and len(session["writes"]) == 1
    assert "work_session" not in project_wide and project_wide["writes"] == []


def test_revoking_one_session_leaves_the_others_open(tmp_path: Path) -> None:
    first, second = project(tmp_path)
    for session in (first, second, None):
        state.open_approval(tmp_path, f"HB-{session or 'PROJ'}"[:15], 20, "", session)
    assert state.revoke_approvals(tmp_path, first) == 1
    assert state.active_approval(tmp_path, first) is None
    assert state.active_approval(tmp_path, second) is not None
    assert state.active_approval(tmp_path) is not None
    assert state.revoke_approvals(tmp_path) == 2
    assert state.active_approval(tmp_path, second) is None


def test_every_approval_path_uses_the_configured_window(tmp_path: Path) -> None:
    first, _ = project(tmp_path, minutes=5)
    native(
        tmp_path, "prompt", {"session_id": "native-a", "prompt": "approve HB-TYPED1"}
    )
    typed = state.active_approval(tmp_path, first)
    assert typed is not None and minutes_open(typed[1]) == 5

    state.revoke_approvals(tmp_path)
    started = decisions.begin(
        tmp_path,
        "d1",
        "Create these 3 work items?",
        ("Approve", "Not now"),
        "chat",
        approval=True,
        work_session_id=first,
    )
    assert isinstance(started, Ok)
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "Approve"})
    decided = state.active_approval(tmp_path, first)
    assert decided is not None and minutes_open(decided[1]) == 5
