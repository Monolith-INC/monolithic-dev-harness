"""Session-start events have a common identity at the host boundary."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness import hook, work_sessions
from host_adapters import conversation_id, start_event
from host_adapters.installation_project import assets


@pytest.mark.parametrize("host", ("claude", "codex"))
def test_supported_hosts_normalize_start_events(host: str) -> None:
    event = start_event(
        host,
        {"session_id": "chat-1", "source": "resume", "hook_event_name": "SessionStart"},
    )

    assert event is not None
    assert (event.conversation, event.source, event.subagent) == (
        "chat-1",
        "resume",
        False,
    )


def test_unsupported_host_and_missing_identity_are_not_start_events() -> None:
    assert start_event("cursor", {"session_id": "chat-1"}) is None
    assert start_event("codex", {"source": "startup"}) is None


def test_cli_conversation_identity_is_only_claimed_when_the_host_provides_it(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")

    assert conversation_id("codex") == "codex-thread"
    assert conversation_id("claude") == ""


def test_subagent_start_is_marked() -> None:
    event = start_event("claude", {"session_id": "chat-1", "agent_id": "child"})

    assert event is not None and event.subagent


def test_start_hook_emits_saved_work_context(tmp_path, monkeypatch, capsys) -> None:
    work_sessions.start(tmp_path, "Review the report")
    monkeypatch.setattr(hook, "_workspace", lambda *_: tmp_path)

    exit_code = hook.handle_session_start(
        "codex", {"session_id": "chat-1", "source": "resume"}
    )

    assert exit_code == 0
    assert '"hookEventName": "SessionStart"' in capsys.readouterr().out


def test_start_hook_never_injects_context_for_subagents(
    tmp_path, monkeypatch, capsys
) -> None:
    work_sessions.start(tmp_path, "Review the report")
    monkeypatch.setattr(hook, "_workspace", lambda *_: tmp_path)

    assert (
        hook.handle_session_start("codex", {"session_id": "chat", "agent_id": "child"})
        == 0
    )
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("host", ("claude", "codex"))
def test_start_event_dispatches_in_hook_process(host: str, tmp_path: Path) -> None:
    work_sessions.start(tmp_path, "Review the report")
    script = Path(hook.__file__)

    result = subprocess.run(
        [sys.executable, str(script), "--host", host, "--event", "session-start"],
        input=json.dumps(
            {"session_id": "chat", "source": "resume", "cwd": str(tmp_path)}
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Review the report" in output["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    ("host", "filename"),
    (("claude", ".claude/settings.local.json"), ("codex", ".codex/hooks.json")),
)
def test_project_installation_keeps_start_event(
    host: str, filename: str, tmp_path: Path
) -> None:
    plugin = Path(hook.__file__).resolve().parents[2]

    configured = assets(host, tmp_path, plugin).value
    document = next(
        item.text for item in configured if item.path == tmp_path / filename
    )
    handlers = json.loads(document)["hooks"]["SessionStart"]

    assert "--event session-start" in handlers[0]["hooks"][0]["command"]
