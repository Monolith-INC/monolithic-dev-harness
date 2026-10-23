"""Synthetic cases using the observed Codex 0.162.1 lifecycle and effect wire shapes."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.result import Err, Ok
from harness import hook, rules, state, work_sessions
from host_adapters import codex_bindings, hook_bridge, work_session_context
from tests.settings_fixture import write_settings


def payload(repo: Path, event: str = "SubagentStart", **changes: object) -> dict:
    return {
        "cwd": str(repo),
        "session_id": "parent-native",
        "agent_id": "child-native",
        "agent_type": "default",
        "hook_event_name": event,
        **changes,
    }


@pytest.fixture
def scoped(tmp_path: Path) -> tuple[Path, str]:
    write_settings(tmp_path, git={"delivery": True, "base_branch": "main"})
    session = work_sessions.start(tmp_path, "DAY-001").value
    work_session_context.bind_session(tmp_path, "codex", "parent-native", session.id)
    return tmp_path, session.id


def test_host_start_pins_existing_parent_scope(scoped: tuple[Path, str]) -> None:
    repo, scope = scoped
    assert isinstance(codex_bindings.observe_lifecycle(repo, payload(repo)), Ok)
    assert codex_bindings.resolve_child_scope(repo, payload(repo)) == Ok(scope)
    assert isinstance(codex_bindings.observe_lifecycle(repo, payload(repo)), Ok)


@pytest.mark.parametrize(
    "event,wire",
    (
        ("subagent-start", "SubagentStart"),
        ("subagent-stop", "SubagentStop"),
        ("interrupt", "Interrupt"),
    ),
)
def test_opted_out_repository_lifecycle_preserves_existing_child_records(
    scoped: tuple[Path, str],
    event: str,
    wire: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    saved = {
        path: path.read_bytes() for path in (repo / codex_bindings.ROOT).glob("*.json")
    }
    (repo / ".harness/settings.json").unlink()
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(repo),
                    "session_id": "parent-native",
                    "hook_event_name": wire,
                    **(
                        {"agent_id": "new-child-native"}
                        if event == "subagent-start"
                        else {}
                    ),
                    **(
                        {"agent_id": "child-native"} if event == "subagent-stop" else {}
                    ),
                }
            )
        ),
    )
    assert hook.main(["--host", "codex", "--event", event]) == 0
    assert {
        path: path.read_bytes() for path in (repo / codex_bindings.ROOT).glob("*.json")
    } == saved


def test_missing_child_binding_does_not_inherit_current(
    scoped: tuple[Path, str],
) -> None:
    repo, _ = scoped
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


@pytest.mark.parametrize(
    "changes",
    (
        {"agent_id": ""},
        {"session_id": ""},
        {"session_id": "unknown"},
        {"cwd": "/elsewhere"},
    ),
)
def test_start_rejects_missing_identity_or_project(
    scoped: tuple[Path, str], changes: dict
) -> None:
    repo, _ = scoped
    assert isinstance(
        codex_bindings.observe_lifecycle(repo, payload(repo, **changes)), Err
    )


def test_scope_conflict_cannot_rebind_child(scoped: tuple[Path, str]) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    other = work_sessions.start(repo, "DAY-002").value
    work_session_context.bind_session(repo, "codex", "other-parent", other.id)
    assert isinstance(
        codex_bindings.observe_lifecycle(
            repo, payload(repo, session_id="other-parent")
        ),
        Err,
    )
    assert isinstance(
        codex_bindings.resolve_child_scope(
            repo, payload(repo, session_id="other-parent")
        ),
        Err,
    )
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


@pytest.mark.parametrize("operation", ("pause", "stop"))
def test_inactive_parent_cannot_spend_approval(
    scoped: tuple[Path, str], operation: str
) -> None:
    repo, scope = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    work_sessions.transition(repo, scope, operation)
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


def test_parent_switch_does_not_move_existing_child(scoped: tuple[Path, str]) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    other = work_sessions.start(repo, "DAY-002").value
    work_session_context.bind_session(repo, "codex", "parent-native", other.id)
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


def test_stop_while_parent_paused_remains_stopped_after_resume(
    scoped: tuple[Path, str],
) -> None:
    repo, scope = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    work_sessions.transition(repo, scope, "pause")
    assert isinstance(
        codex_bindings.observe_lifecycle(repo, payload(repo, "SubagentStop")), Ok
    )
    work_sessions.transition(repo, scope, "resume")
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


def test_stop_is_idempotent_and_start_cannot_revive_child(
    scoped: tuple[Path, str],
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    assert isinstance(
        codex_bindings.observe_lifecycle(repo, payload(repo, "SubagentStop")), Ok
    )
    assert isinstance(
        codex_bindings.observe_lifecycle(repo, payload(repo, "SubagentStop")), Ok
    )
    assert isinstance(codex_bindings.observe_lifecycle(repo, payload(repo)), Err)
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


def test_interrupt_revokes_children_without_claiming_cancel(
    scoped: tuple[Path, str],
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    assert isinstance(
        codex_bindings.interrupt(
            repo, {"session_id": "parent-native", "cwd": str(repo)}
        ),
        Ok,
    )
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


def test_corrupt_neighbor_does_not_prevent_interrupt_revocation(
    scoped: tuple[Path, str],
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    (repo / codex_bindings.ROOT / "corrupt.json").write_text("invalid")
    codex_bindings.interrupt(repo, {"cwd": str(repo), "session_id": "parent-native"})
    assert isinstance(codex_bindings.resolve_child_scope(repo, payload(repo)), Err)


@pytest.mark.parametrize("event", ("prompt", "answer", "ask", "startup"))
def test_child_cannot_record_human_authority(
    scoped: tuple[Path, str],
    event: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps(payload(repo, prompt="approve HB-ABCD")))
    )
    assert hook.main(["--host", "codex", "--event", event]) == 0
    assert "codex-child-authority" in capsys.readouterr().out


@pytest.mark.parametrize(
    "command",
    (
        "begin --request x",
        "work-session select WS-other",
        "decision present --gate publish-branch",
        "workflow checkpoint --session-id WS-other",
    ),
)
def test_child_cannot_use_harness_to_change_scope(
    scoped: tuple[Path, str], command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(
            repo,
            "PreToolUse",
            tool_name="Bash",
            tool_input={
                "command": f"{Path(hook.PLUGIN_ROOT) / 'bin/harness'} {command}"
            },
        ),
    )
    assert "codex-child-authority" in capsys.readouterr().out


def test_binding_records_are_human_owned() -> None:
    assert rules.is_human_owned(
        ".harness/state/host_sessions/codex/children/child.json"
    )


@pytest.mark.parametrize(
    "arguments,allowed",
    (
        ("-m pytest tests/harness/test_work_session_context.py -q", True),
        ("-m platform", True),
        ("-m harness.cli work-session select WS-other", False),
        ("scripts/harness/cli.py decision present --gate publish-branch", False),
    ),
)
def test_child_runtime_runner_preserves_tests_and_blocks_controls(
    scoped: tuple[Path, str],
    arguments: str,
    allowed: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    delegate = Mock(return_value=0)
    monkeypatch.setattr(hook, "_delegate_to_workflow_policy", delegate)
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(
            repo,
            "PreToolUse",
            tool_name="Bash",
            tool_input={
                "command": f"{Path(hook.PLUGIN_ROOT) / 'bin/harness-python'} {arguments}"
            },
        ),
    )
    assert delegate.called == allowed
    assert ("codex-child-authority" in capsys.readouterr().out) != allowed


def test_child_runtime_runner_cannot_execute_host_hooks(
    scoped: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    delegate = Mock(return_value=0)
    monkeypatch.setattr(hook, "_delegate_to_workflow_policy", delegate)
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(
            repo,
            "PreToolUse",
            tool_name="Bash",
            tool_input={
                "command": f"{Path(hook.PLUGIN_ROOT) / 'bin/harness-python'} {Path(hook.__file__)} --host codex --event prompt"
            },
        ),
    )
    assert not delegate.called
    assert "hook-entry" in capsys.readouterr().out


def test_effect_uses_parent_scope_when_project_current_differs(
    scoped: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, scope = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    work_sessions.start(repo, "DAY-002")
    evaluate = Mock(return_value=rules.Decision.allow())
    delegate = Mock(return_value=0)
    monkeypatch.setattr(hook.rules, "evaluate", evaluate)
    monkeypatch.setattr(hook, "_delegate_to_workflow_policy", delegate)
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(
            repo,
            "PreToolUse",
            tool_name="apply_patch",
            tool_input={
                "command": "*** Begin Patch\n*** Add File: lib/a.py\n+x\n*** End Patch"
            },
        ),
    )
    assert evaluate.call_args.args[4] == scope
    assert delegate.call_args.args[1]["session_id"] == "parent-native"


@pytest.mark.parametrize(
    "changes",
    (
        {"agent_id": ""},
        {"agent_type": "worker", "agent_id": None},
        {"parent_thread_id": "parent", "agent_id": None},
    ),
)
def test_ambiguous_child_effect_is_denied(
    scoped: tuple[Path, str], changes: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _ = scoped
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(
            repo,
            "PreToolUse",
            tool_name="apply_patch",
            tool_input={
                "command": "*** Begin Patch\n*** Add File: x\n+x\n*** End Patch"
            },
            **changes,
        ),
    )
    assert "codex-child-lineage" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name", ("apply_patch", "functions.apply_patch", "functionsapply_patch")
)
def test_patch_alias_paths_reach_common_policy(tmp_path: Path, name: str) -> None:
    call = hook_bridge.parse_tool_call(
        "codex",
        "pre-tool",
        {
            "cwd": str(tmp_path),
            "tool_name": name,
            "tool_input": {
                "command": "*** Begin Patch\n*** Add File: .harness/state/host_sessions/codex/children/fake.json\n+x\n*** End Patch"
            },
        },
    )
    assert call.kind == "edit"
    assert call.file_paths == (
        str(tmp_path / ".harness/state/host_sessions/codex/children/fake.json"),
    )
    assert not rules.rule_human_owned(call, tmp_path).allowed


def test_lifecycle_hooks_and_native_control_matchers_are_registered() -> None:
    hooks = json.loads((Path(hook.PLUGIN_ROOT) / "hooks/codex.hooks.json").read_text())[
        "hooks"
    ]
    assert {"SubagentStart", "SubagentStop", "Interrupt"}.issubset(hooks)
    assert "collaboration.*" in hooks["PreToolUse"][0]["matcher"]


@pytest.mark.parametrize(
    "command",
    (
        "bin/har''ness work-session select other",
        "sh -c 'harness begin --request x'",
        "python -m harness.cli decision present",
    ),
)
def test_wrapped_child_control_commands_are_denied(
    scoped: tuple[Path, str], command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(repo, "PreToolUse", tool_name="Bash", tool_input={"command": command}),
    )
    assert "codex-child-authority" in capsys.readouterr().out


def test_root_profile_is_observed_and_child_cannot_replace_it(
    scoped: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from host_adapters import codex_runtime

    repo, _ = scoped
    observe = Mock(wraps=codex_runtime.persist_observation)
    monkeypatch.setattr(codex_runtime, "persist_observation", observe)
    monkeypatch.setattr(hook, "handle_pre_tool", Mock(return_value=0))
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "cwd": str(repo),
                    "session_id": "parent-native",
                    "tool_name": "Bash",
                    "hook_event_name": "PreToolUse",
                    "tool_input": {"command": "pwd"},
                }
            )
        ),
    )
    assert hook.main(["--host", "codex", "--event", "pre-tool"]) == 0
    assert observe.call_count == 1
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                payload(
                    repo, "PreToolUse", tool_name="Bash", tool_input={"command": "pwd"}
                )
            )
        ),
    )
    assert hook.main(["--host", "codex", "--event", "pre-tool"]) == 0
    assert observe.call_count == 1


@pytest.mark.parametrize("child", (False, True))
@pytest.mark.parametrize(
    "tool_input,law",
    (
        ({"command": "git rebase main"}, "history-preserved"),
        (
            {
                "command": "printf forged > .harness/state/host_sessions/codex/children/fake.json"
            },
            "human-owned",
        ),
    ),
)
def test_root_and_child_use_existing_laws(
    scoped: tuple[Path, str],
    child: bool,
    tool_input: dict,
    law: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = scoped
    codex_bindings.observe_lifecycle(repo, payload(repo))
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        {
            **{
                "cwd": str(repo),
                "session_id": "parent-native",
                "tool_name": "Bash",
                "tool_input": tool_input,
            },
            **({"agent_id": "child-native"} if child else {}),
        },
    )
    assert law in capsys.readouterr().out


@pytest.mark.parametrize(
    "tool_input",
    (
        {"command": "pwd"},
        {"command": "harness begin --request x"},
    ),
)
def test_suspended_repository_releases_invalid_lineage_and_controls(
    scoped: tuple[Path, str],
    tool_input: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _ = scoped
    state.set_harness_mode(repo, "suspended")
    emit = Mock()
    monkeypatch.setattr(hook, "_emit_decision", emit)
    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        payload(
            repo,
            "PreToolUse",
            session_id="unknown-parent",
            agent_id=None,
            tool_name="Bash",
            tool_input=tool_input,
        ),
    )
    assert emit.call_args.args == ("codex", rules.Decision.allow())
