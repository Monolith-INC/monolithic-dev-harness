"""A turn never ends mid-workflow with nothing for the user to answer."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, state, work_sessions, workflow
from host_adapters import work_session_context
from tests.settings_fixture import write_settings

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / "scripts/harness/hook.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    session = work_sessions.start(tmp_path, "DAY-003").value.id
    assert isinstance(
        work_session_context.bind_session(tmp_path, "claude", "chat-1", session), Ok
    )
    started = workflow.start("DAY-003: share a list").value
    planned = workflow.add_point(
        started, "Plan drafted", "discover", (), (), "", "Ask the open questions", ()
    ).value
    assert isinstance(workflow.save(tmp_path, planned, session), Ok)
    return tmp_path


def stop(repo: Path, message: str, **extra: object) -> str:
    payload = {
        "cwd": str(repo),
        "session_id": "chat-1",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": message,
        **extra,
    }
    result = subprocess.run(
        [sys.executable, str(HOOK), "--host", "claude", "--event", "stop"],
        input=json.dumps(payload),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return result.stdout


def session_of(repo: Path) -> str:
    return work_sessions.list_sessions(repo).value[0].id


def test_a_silent_stop_is_sent_back_with_the_next_action(repo: Path) -> None:
    out = json.loads(stop(repo, "Both choices are saved. Next: supported devices."))
    assert out["decision"] == "block"
    assert "Ask the open questions" in out["reason"]


def test_a_question_to_the_user_ends_the_turn(repo: Path) -> None:
    assert stop(repo, "Which phones should shared lists support?") == ""
    assert (
        stop(repo, "1. **Service?**\n   a. Firebase\n\nReply in any form.\n**Ready?**")
        == ""
    )


def test_a_pending_menu_ends_the_turn(repo: Path) -> None:
    decisions.begin(
        repo,
        "d1",
        "Continue?",
        ("Continue", "Stop"),
        "chat",
        work_session_id=session_of(repo),
    )
    assert stop(repo, "The plan is ready.") == ""


def test_the_guard_sends_the_agent_back_only_once(repo: Path) -> None:
    assert stop(repo, "Saved.", stop_hook_active=True) == ""


def test_a_finished_workflow_may_stop(repo: Path) -> None:
    current = workflow.load(repo, session_of(repo)).value
    workflow.save(repo, workflow.complete(current).value, session_of(repo))
    assert stop(repo, "Done.") == ""


def test_a_suspended_harness_does_not_nudge(repo: Path) -> None:
    state.set_harness_mode(repo, "suspended")
    assert stop(repo, "Saved.") == ""
