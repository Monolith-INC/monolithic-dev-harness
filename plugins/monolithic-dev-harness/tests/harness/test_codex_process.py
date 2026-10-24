"""Adapter identity and the standard command channel, using synthetic native events."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.result import Ok
from harness import cli, hook, process_bus, work_sessions
from harness.process_messages import Context, ProcessStatus
from host_adapters import (
    codex_bindings,
    codex_process,
    hook_bridge,
    work_session_context,
)
from tests.settings_fixture import write_settings


def native(repo: Path, **fields) -> dict:
    return {
        "cwd": str(repo),
        "session_id": "main",
        "hook_event_name": "PreToolUse",
        "turn_id": "execution",
        "tool_use_id": "tool-1",
        **fields,
    }


@pytest.fixture
def running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Context]:
    write_settings(tmp_path)
    session = work_sessions.start(tmp_path, "process bridge proof").value
    work_session_context.bind_session(tmp_path, "codex", "main", session.id)
    assert isinstance(
        codex_bindings.observe_lifecycle(
            tmp_path,
            native(
                tmp_path,
                hook_event_name="SubagentStart",
                agent_id="worker",
                agent_type="default",
            ),
        ),
        Ok,
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "main")
    return tmp_path, Context("codex", "main", session.id)


def command(repo: Path, text: str, **fields) -> dict:
    return native(repo, tool_name="Bash", tool_input={"command": text}, **fields)


def apply(repo: Path, payload: dict):
    return codex_process.before_tool(
        repo, payload, hook_bridge.parse_tool_call("codex", "pre-tool", payload)
    )


def test_native_start_publishes_standard_process_record(running) -> None:
    repo, ctx = running
    record = process_bus.get_record(repo, ctx, "worker").value
    assert record.runtime_status == ProcessStatus.RUNNING and not record.revoked


def test_main_agent_report_is_distinct_from_host_confirmation(running, capsys) -> None:
    repo, ctx = running
    assert (
        apply(repo, command(repo, "harness process report worker --status interrupted"))
        is None
    )
    record = process_bus.get_record(repo, ctx, "worker").value
    assert record.reported_status == ProcessStatus.INTERRUPTED
    assert record.runtime_status == ProcessStatus.RUNNING and not record.revoked
    assert (
        cli.main(
            [
                "process",
                "report",
                "worker",
                "--status",
                "interrupted",
                "--host",
                "codex",
                "--repo",
                str(repo),
            ]
        )
        == 0
    )
    assert not json.loads(capsys.readouterr().out)["runtime_stopped"]


def test_cli_cannot_mutate_without_adapter_observation(running, capsys) -> None:
    repo, ctx = running
    assert (
        cli.main(
            ["process", "cancel", "worker", "--host", "codex", "--repo", str(repo)]
        )
        == 2
    )
    assert "not applied" in capsys.readouterr().err
    assert not process_bus.get_record(repo, ctx, "worker").value.revoked


def test_cancel_channel_withdraws_permission_without_native_interrupt(
    running, capsys
) -> None:
    repo, ctx = running
    payload = command(
        repo, f'harness process cancel worker --host codex --repo "{repo}"'
    )
    assert apply(repo, payload) is None
    assert apply(repo, payload) is None
    record = process_bus.get_record(repo, ctx, "worker").value
    assert record.revoked and record.runtime_status == ProcessStatus.RUNNING
    assert (
        cli.main(
            ["process", "cancel", "worker", "--host", "codex", "--repo", str(repo)]
        )
        == 0
    )
    reply = json.loads(capsys.readouterr().out)
    assert reply["permission_revoked"] and not reply["runtime_stopped"]
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        command(
            repo, "printf changed > output.txt", agent_id="worker", agent_type="default"
        ),
    )
    assert "codex-child-lineage" in capsys.readouterr().out


@pytest.mark.parametrize(
    "extra",
    (
        "--session-id wrong",
        "--host claude",
        "--repo /elsewhere",
        "--nonsense value",
        "--host codex --host codex",
    ),
)
def test_invalid_cancellation_scope_does_not_withdraw(running, extra: str) -> None:
    repo, ctx = running
    assert not apply(
        repo, command(repo, f"harness process cancel worker {extra}")
    ).allowed
    assert not process_bus.get_record(repo, ctx, "worker").value.revoked


@pytest.mark.parametrize(
    "fields",
    ({"tool_use_id": ""}, {"agent_id": "worker"}, {"session_id": "someone-else"}),
)
def test_untrusted_or_subagent_sender_cannot_cancel(running, fields) -> None:
    repo, ctx = running
    assert not apply(
        repo, command(repo, "harness process cancel worker", **fields)
    ).allowed
    assert not process_bus.get_record(repo, ctx, "worker").value.revoked


def test_root_hook_routes_generic_cancellation_while_question_pending(
    running, capsys, monkeypatch
) -> None:
    repo, ctx = running
    monkeypatch.setattr("harness.decisions.blocking", lambda *args: True)
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        command(repo, f'harness process cancel worker --repo "{repo}"'),
    )
    assert "decision-pending" not in capsys.readouterr().out
    assert process_bus.get_record(repo, ctx, "worker").value.revoked


def test_subagent_and_other_root_cannot_read_owned_command_records(
    running, capsys, monkeypatch
) -> None:
    repo, _ = running
    work_session_context.bind_session(
        repo, "codex", "other", work_sessions.start(repo, "other work").value.id
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "other")
    assert (
        cli.main(
            ["process", "status", "worker", "--host", "codex", "--repo", str(repo)]
        )
        == 2
    )
    assert "another" in capsys.readouterr().err


def test_suspension_bypass_does_not_publish_cancellation(running, capsys) -> None:
    from harness import state

    repo, ctx = running
    state.set_harness_mode(repo, "suspended")
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        command(repo, f'harness process cancel worker --repo "{repo}"'),
    )
    assert not process_bus.get_record(repo, ctx, "worker").value.revoked
    assert capsys.readouterr().out == ""


def test_unknown_process_flags_are_not_silently_accepted(running) -> None:
    repo, _ = running
    with pytest.raises(SystemExit) as failure:
        cli.main(["process", "list", "--repo", str(repo), "--no-such-flag"])
    assert failure.value.code == 2
