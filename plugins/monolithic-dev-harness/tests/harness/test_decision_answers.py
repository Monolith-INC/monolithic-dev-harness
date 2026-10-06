"""A pending decision is answered only by an offered choice; the user's other commands still work."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import decisions, state, work_sessions
from host_adapters import work_session_context
from tests.harness.test_hook_security import HARNESS, run_hook
from tests.settings_fixture import write_settings


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    return tmp_path


def type_prompt(repo: Path, prompt: str, host: str = "codex", session: str = "") -> str:
    payload = {"prompt": prompt, **({"session_id": session} if session else {})}
    return run_hook(repo, "prompt", payload, host=host)


def chat_decision(
    repo: Path, session: str | None = None, approval: bool = False
) -> None:
    decisions.begin(
        repo,
        "d1",
        "Continue with this plan?",
        ("Continue", "Stop"),
        "chat",
        approval=approval,
        work_session_id=session,
    )


def test_other_messages_leave_the_decision_pending(repo: Path) -> None:
    chat_decision(repo)
    type_prompt(repo, "What does this plan change?")
    assert decisions.waiting(repo)
    type_prompt(repo, "continue.")
    assert (decisions.record(repo) or {}).get("answer") == "Continue"


def test_revoke_suspend_and_typed_approvals_still_work(repo: Path) -> None:
    state.open_approval(repo, "HB-OPEN1", 20)
    chat_decision(repo)
    type_prompt(repo, "harness revoke")
    assert state.active_approval(repo) is None
    type_prompt(repo, "approve HB-TYPED1")
    assert state.active_approval(repo) is not None
    type_prompt(repo, "harness suspend")
    assert state.harness_mode(repo) == "suspended"
    assert decisions.waiting(repo)


def test_cursor_answers_the_one_pending_session_decision(repo: Path) -> None:
    session = work_sessions.start(repo, "DAY-001").value.id
    chat_decision(repo, session)
    type_prompt(repo, "Continue", host="cursor")
    assert (decisions.record(repo, session) or {}).get("answer") == "Continue"


def test_an_approval_covers_the_conversation_that_gave_it(repo: Path) -> None:
    session = work_sessions.start(repo, "DAY-001").value.id
    work_session_context.bind_session(repo, "codex", "native-a", session)
    decisions.begin(
        repo,
        "d1",
        "Publish these items?",
        ("Approve", "Not now"),
        "chat",
        approval=True,
    )
    type_prompt(repo, "Approve", session="native-a")
    assert state.active_approval(repo, session) is not None
    assert state.active_approval(repo) is None


def test_a_wordy_chat_approval_is_refused(repo: Path) -> None:
    result = subprocess.run(
        [
            str(HARNESS),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--host",
            "codex",
            "--approval",
            "--question",
            "Should I edit lib/main.dart and lib/other.dart, and also rename "
            "`FooBarService` in the tracker?",
            "--option",
            "Approve",
            "--option",
            "Not now",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert not decisions.waiting(repo)
