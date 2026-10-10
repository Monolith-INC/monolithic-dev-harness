"""An agent cannot step around a pending decision or answer for the user.

Each case is an attack the 0.6.0 review reproduced against the real hook.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.result import Err
from harness import decisions, rules, state, work_sessions
from host_adapters import work_session_context
from integrations import gateway
from tests.settings_fixture import write_settings

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / "scripts" / "harness" / "hook.py"
HARNESS = PLUGIN / "bin" / "harness"


@pytest.mark.parametrize(
    "command",
    (
        f"cat {HOOK}",
        f"sed -n '1,80p' {HOOK}",
        f"rg 'harness.hook' {HOOK}",
        f"cat {HOOK}; sed -n '1,80p' {HOOK}",
    ),
)
def test_reading_hook_source_is_allowed(command: str) -> None:
    assert not rules.runs_harness_hook(command)


def test_reader_does_not_hide_hook_execution() -> None:
    assert rules.runs_harness_hook(f"cat {HOOK}; python3 {HOOK} --event prompt")


@pytest.mark.parametrize("operation", ("check", "format"))
def test_ruff_maintains_hook_source_without_running_it(operation: str) -> None:
    assert not rules.runs_harness_hook(f"ruff {operation} {HOOK}")
    assert rules.runs_harness_hook(
        f"ruff {operation} {HOOK}; python3 {HOOK} --event prompt"
    )


@pytest.mark.parametrize("operation", ("diff", "show", "status"))
def test_git_inspects_hook_source_without_running_it(operation: str) -> None:
    assert not rules.runs_harness_hook(f"git {operation} -- {HOOK}")
    assert rules.runs_harness_hook(
        f"git {operation} -- {HOOK}; python3 {HOOK} --event prompt"
    )
    assert rules.runs_harness_hook(f"git {operation} --ext-diff -- {HOOK}")


@pytest.mark.parametrize("prefix", ("git", "git -c core.filemode=false", "git -C /tmp"))
def test_git_stages_hook_source_without_running_it(prefix: str) -> None:
    assert not rules.runs_harness_hook(f"{prefix} add -- {HOOK}")
    assert rules.runs_harness_hook(
        f"{prefix} add -- {HOOK}; python3 {HOOK} --event prompt"
    )
    assert rules.runs_harness_hook(
        f"{prefix} add -- {HOOK} $(python3 {HOOK} --event prompt)"
    )


def test_git_staging_does_not_allow_executable_configuration() -> None:
    assert rules.runs_harness_hook(
        f"git -c core.fsmonitor='python3 {HOOK} --event prompt' add -- {HOOK}"
    )
    assert rules.runs_harness_hook(
        f"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fsmonitor GIT_CONFIG_VALUE_0='python3 {HOOK} --event prompt' git add -- {HOOK}"
    )
    assert rules.runs_harness_hook(
        f"env GIT_CONFIG_GLOBAL=/tmp/execute-hook.config git add -- {HOOK}"
    )
    assert rules.runs_harness_hook(
        f"env GIT_''CONFIG_COUNT=1 GIT_''CONFIG_KEY_0=core.fsmonitor GIT_''CONFIG_VALUE_0='python3 {HOOK} --event prompt' git add -- {HOOK}"
    )
    assert rules.runs_harness_hook(
        f"env -S \"GIT_''CONFIG_GLOBAL=/tmp/execute-hook.config git add -- {HOOK}\""
    )
    assert rules.runs_harness_hook(
        f"/usr/bin/env -S \"GIT_''CONFIG_GLOBAL=/tmp/execute-hook.config git add -- {HOOK}\""
    )
    assert rules.runs_harness_hook(
        f"sh <<'SCRIPT'\nenv GIT_CONFIG_GLOBAL=/tmp/execute-hook.config git add -- {HOOK}\nSCRIPT"
    )
    assert rules.runs_harness_hook(f". /tmp/execute-hook.config; git add -- {HOOK}")


@pytest.mark.parametrize(
    "mode", ("-e", "--edit", "-i", "--interactive", "-p", "--patch", "-ve", "--ed")
)
def test_git_staging_cannot_execute_hooks_through_an_editor(mode: str) -> None:
    assert rules.runs_harness_hook(
        f"GIT_EDITOR='python3 {HOOK} --host codex --event prompt #' git add {mode} -- {HOOK} < reply.json"
    )


@pytest.mark.parametrize(
    "command",
    (
        "cat notes.txt",
        "sed -n '1,80p' notes.txt",
        "rg 'capture' notes.txt",
        f"cat {HOOK}",
        f"{HARNESS} suspension status",
    ),
)
def test_pending_decision_allows_diagnostics(project, command: str) -> None:
    assert "decision-pending" not in bash(project[0], command)


@pytest.mark.parametrize(
    "command",
    (
        "cat notes.txt > copied.txt",
        "sed -i 's/a/b/' notes.txt",
        "cat notes.txt; touch changed.txt",
        f"{HARNESS} suspension status; touch changed.txt",
    ),
)
def test_pending_decision_still_blocks_diagnostic_writes(project, command: str) -> None:
    assert "decision-pending" in bash(project[0], command)


def test_prompt_failure_is_reported_without_exposing_payload(
    monkeypatch, capsys
) -> None:
    from io import StringIO

    from harness import hook

    monkeypatch.setattr(sys, "stdin", StringIO('{"prompt": "private reply"}'))
    monkeypatch.setattr(hook, "handle_prompt", lambda *_: {}["private error"])
    assert hook.main(["--host", "codex", "--event", "prompt"]) == 0
    assert (
        "human reply capture failed (codex, prompt): KeyError"
        in capsys.readouterr().err
    )


def run_hook(repo: Path, event: str, payload: dict, host: str = "codex") -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK), "--host", host, "--event", event],
        input=json.dumps({"cwd": str(repo), **payload}),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, str, str]:
    """A governed project; conversation native-a works on WS-1, which awaits an answer."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    first = work_sessions.start(tmp_path, "DAY-001").value.id
    second = work_sessions.start(tmp_path, "DAY-002").value.id
    work_session_context.bind_session(tmp_path, "codex", "native-a", first)
    decisions.begin(
        tmp_path,
        "d1",
        "Publish these items?",
        ("Approve", "Revise"),
        "chat",
        approval=True,
        work_session_id=first,
    )
    return tmp_path, first, second


def bash(repo: Path, command: str, session: str = "native-a") -> str:
    return run_hook(
        repo,
        "pre-tool",
        {
            "session_id": session,
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )


def test_switching_session_cannot_escape_a_pending_decision(project) -> None:
    repo, first, second = project
    assert "decision-pending" in bash(repo, "touch notes.txt")
    for command in (
        f"{HARNESS} work-session select {second}",
        f"{HARNESS} work-session select {second} && touch notes.txt",
        f"harness work-session select {second} && touch notes.txt",
    ):
        assert "deny" in bash(repo, command), command
    assert (
        work_session_context.resolve_session(repo, "codex", "native-a").value == first
    )
    assert "decision-pending" in bash(repo, "touch notes.txt")


def test_running_the_hooks_directly_is_refused(project) -> None:
    repo, _, _ = project
    payload = json.dumps({"cwd": str(repo), "prompt": "Approve"}).replace('"', '\\"')
    for command in (
        f'echo "{payload}" | python3 {HOOK} --host codex --event prompt',
        f"python3 {HOOK} --host codex --event prompt < reply.json",
        f"cd {HOOK.parent} && python3 hook.py --host codex --event prompt",
        f"cp {HOOK} /tmp/h.py",
        "python3 -c 'import hook_runtime'",
        "python3 -c 'from harness import hook'",
    ):
        assert "hook-entry" in bash(repo, command, session="native-x"), command
    record = decisions.record(repo, project[1]) or {}
    assert record.get("status") == "pending"
    assert state.active_approval(repo, project[1]) is None


def test_a_command_for_another_session_is_refused(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    first = work_sessions.start(tmp_path, "DAY-001").value.id
    second = work_sessions.start(tmp_path, "DAY-002").value.id
    work_session_context.bind_session(tmp_path, "codex", "native-a", first)
    out = bash(
        tmp_path, f"{HARNESS} workflow checkpoint --label x --session-id {second}"
    )
    assert "work-session-mismatch" in out
    allowed = bash(tmp_path, f"{HARNESS} work-session select {second}")
    assert "deny" not in allowed
    assert work_session_context.resolve_session(
        tmp_path, "codex", "native-a"
    ).value == (second)


def test_cursor_shell_events_wait_for_any_pending_decision(project) -> None:
    repo, _, _ = project
    out = run_hook(repo, "shell", {"command": "touch a.txt"}, host="cursor")
    assert "deny" in out


def test_the_gateway_holds_writes_for_a_session_decision(project) -> None:
    repo, _, _ = project
    result = gateway.handle_call(
        "tracker_create_work_item",
        {"kind": "user_story", "title": "t", "description": "d"},
        repo,
    )
    assert isinstance(result, Err)
    assert result.failure.code == "decision_pending"
