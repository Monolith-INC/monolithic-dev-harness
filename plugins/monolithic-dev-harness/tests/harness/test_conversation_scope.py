"""A conversation with no link to a work session acts in the project's current one, as its commands do."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.result import Ok
from harness import state, work_sessions
from host_adapters import work_session_context
from tests.harness.test_approval_scope import WRITE
from tests.harness.test_decisions import CLI, native
from tests.harness.test_hook_rules import SETTINGS
from tests.settings_fixture import write_settings

BRANCH = "feat/x"
GATE = ("--gate", "publish-branch", "--value", f"branch={BRANCH}")


def project(tmp_path: Path) -> tuple[str, str]:
    """A governed checkout with two active work sessions: the project's current one, whose
    conversation is native-a, and another one, whose conversation is native-c."""
    subprocess.run(["git", "init", "-q", "-b", BRANCH, str(tmp_path)], check=True)
    write_settings(tmp_path, tracker=SETTINGS["tracker"], scm=SETTINGS["scm"])
    state.set_tracking_mode(tmp_path, "skipped")
    other = work_sessions.start(tmp_path, "DAY-001").value.id
    current = work_sessions.start(tmp_path, "DAY-002").value.id
    for native_id, session in (("native-a", current), ("native-c", other)):
        assert isinstance(
            work_session_context.bind_session(tmp_path, "codex", native_id, session),
            Ok,
        )
    return current, other


def ask(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "decision", "present", "--repo", str(repo), *GATE, *extra],
        capture_output=True,
        text=True,
        timeout=30,
    )


def present(repo: Path, *extra: str) -> dict:
    return json.loads(ask(repo, *extra).stdout)


def approve(repo: Path, native_id: str | None) -> None:
    assert present(repo)["state"] == "waiting_for_human"
    session = {"session_id": native_id} if native_id else {}
    native(repo, "prompt", {**session, "prompt": "approve"})


def command(repo: Path, native_id: str, shell: str) -> str:
    return native(
        repo,
        "pre-tool",
        {
            "tool_name": "Bash",
            "tool_input": {"command": shell},
            "session_id": native_id,
        },
    )


def push(repo: Path, native_id: str) -> str:
    return command(repo, native_id, f"git push origin {BRANCH}")


def test_a_conversation_with_no_link_is_covered_by_the_current_sessions_approval(
    tmp_path: Path,
) -> None:
    current, _ = project(tmp_path)
    approve(tmp_path, "native-a")
    assert state.active_approval(tmp_path, current) is not None
    assert "deny" not in push(tmp_path, "native-a")
    assert "deny" not in push(tmp_path, "native-resumed")


def test_the_gate_answers_already_answered_only_where_the_hook_accepts_it(
    tmp_path: Path,
) -> None:
    project(tmp_path)
    approve(tmp_path, "native-a")
    assert present(tmp_path)["state"] == "already_answered"
    assert "deny" not in push(tmp_path, "native-resumed")
    assert "deny" not in push(tmp_path, "native-a")


def test_an_approval_given_by_a_conversation_with_no_link_is_the_current_sessions(
    tmp_path: Path,
) -> None:
    current, _ = project(tmp_path)
    approve(tmp_path, "native-resumed")
    ((_, record),) = state.open_approvals(tmp_path, current)
    assert record["work_session"] == current
    assert present(tmp_path)["state"] == "already_answered"
    assert "deny" not in push(tmp_path, "native-resumed")
    assert "deny" not in push(tmp_path, "native-a")


def test_a_typed_approval_from_a_conversation_with_no_link_is_the_current_sessions(
    tmp_path: Path,
) -> None:
    current, _ = project(tmp_path)
    native(
        tmp_path,
        "prompt",
        {"session_id": "native-resumed", "prompt": "approve HB-TEST1"},
    )
    assert state.active_approval(tmp_path, current) is not None
    assert state.active_approval(tmp_path) is None
    assert "deny" not in native(
        tmp_path, "pre-tool", {**WRITE, "session_id": "native-resumed"}
    )


def test_a_conversation_in_another_session_is_not_covered_and_the_gate_asks_again(
    tmp_path: Path,
) -> None:
    current, other = project(tmp_path)
    approve(tmp_path, "native-a")
    unnamed = (
        f"{CLI} decision present --repo {tmp_path} --gate publish-branch "
        f"--value branch={BRANCH}"
    )
    assert "approval-required" in push(tmp_path, "native-c")
    refused = command(tmp_path, "native-c", unnamed)
    assert "work-session-mismatch" in refused and f"--session-id {other}" in refused
    assert "deny" not in command(tmp_path, "native-a", unnamed)
    assert "deny" not in command(tmp_path, "native-resumed", unnamed)
    named = command(tmp_path, "native-c", f"{unnamed} --session-id {other}")
    assert "deny" not in named
    assert present(tmp_path, "--session-id", other)["state"] == "waiting_for_human"
    assert state.active_approval(tmp_path, current) is not None
