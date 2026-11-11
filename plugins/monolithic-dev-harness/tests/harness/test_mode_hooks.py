"""The mode hooks act only while a mode is active and its manifest lists them.

`orient` puts the mode's rules in the prompt's context; `operations` refuses a gateway tool the mode
does not list. The tests run in-process, with `modes.MODES_ROOT` pointed at fixture folders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, hook, mode_hooks, modes, rules, state, work_sessions
from host_adapters import work_session_context
from tests.harness.test_mode_session import entered
from tests.harness.test_modes import with_fields, write_mode
from tests.settings_fixture import write_settings

GATEWAY = "mcp__plugin_monolithic-dev-harness_workflow-integrations__"
LISTED = "tracker_publish_artifact"
LISTED_READ = "tracker_describe"
UNLISTED_READ = "tracker_preflight"
UNLISTED_WRITE = "tracker_update_work_item"
OPERATIONS = [LISTED, LISTED_READ]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    modes_root = tmp_path / "modes"
    write_mode(modes_root, name="fixture", fields=with_fields(operations=OPERATIONS))
    write_mode(
        modes_root,
        name="orient-only",
        fields=with_fields(name="orient-only", hooks=["orient"], operations=OPERATIONS),
    )
    write_mode(
        modes_root,
        name="operations-only",
        fields=with_fields(
            name="operations-only", hooks=["operations"], operations=OPERATIONS
        ),
    )
    monkeypatch.setattr(modes, "MODES_ROOT", modes_root)
    write_settings(project)
    return project


def gateway(tool: str) -> rules.ToolCall:
    return rules.make_call(
        tool, {}, "plugin_monolithic-dev-harness_workflow-integrations", kind="mcp"
    )


def pre_tool_reason(
    project: Path,
    tool: str,
    capsys: pytest.CaptureFixture[str],
    conversation: str | None = None,
) -> str | None:
    """The deny reason the hook prints for a gateway call, or None when it allows the call."""
    hook.handle_pre_tool(
        "claude",
        "pre-tool",
        {
            "cwd": str(project),
            "tool_name": GATEWAY + tool,
            "tool_input": {},
            **({"session_id": conversation} if conversation else {}),
        },
    )
    out = capsys.readouterr().out.strip()
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"].get("permissionDecisionReason")


# orient


def test_orient_is_silent_without_a_mode(repo: Path) -> None:
    assert mode_hooks.orient(repo) is None


def test_orient_gives_the_mode_and_its_rules_inside_one(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))

    text = mode_hooks.orient(repo)

    assert text is not None
    assert text.startswith("[harness] mode: fixture. Rules:")
    assert "# fixture" in text


def test_orient_is_silent_when_the_manifest_does_not_list_it(repo: Path) -> None:
    entered(modes.enter(repo, "operations-only"))

    assert mode_hooks.orient(repo) is None


def test_the_prompt_carries_the_mode_rules(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )

    assert "[harness] mode: fixture. Rules:" in capsys.readouterr().out


def test_a_failing_orient_drops_neither_the_prompt_nor_its_approval(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    (repo.parent / "modes" / "fixture" / "rules.md").write_bytes(b"\xff\xfe")

    hook.handle_prompt(
        "claude",
        {"cwd": str(repo), "prompt": "approve HB-ABCD1234", "session_id": "chat-a"},
    )

    out = capsys.readouterr().out
    assert "approval HB-ABCD1234 recorded" in out
    assert "[harness] mode:" not in out
    assert state.open_approvals(repo, active.session_id)


# operations


def test_operations_is_silent_without_a_mode(repo: Path) -> None:
    assert mode_hooks.operations(gateway(UNLISTED_READ), repo) is None


def test_operations_refuses_an_unlisted_gateway_tool_inside_the_mode(
    repo: Path,
) -> None:
    entered(modes.enter(repo, "fixture"))

    decision = mode_hooks.operations(gateway(UNLISTED_WRITE), repo)

    assert decision is not None
    assert decision.allowed is False
    assert decision.rule == "mode-operations"
    assert "fixture" in (decision.reason or "")
    assert LISTED in (decision.reason or "")


def test_operations_allows_a_listed_gateway_tool(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))

    assert mode_hooks.operations(gateway(LISTED), repo) is None


def test_operations_ignores_tools_outside_the_gateway(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))
    other = rules.make_call("save_issue", {}, "linear", kind="mcp")

    assert mode_hooks.operations(other, repo) is None


def test_operations_is_silent_when_the_manifest_does_not_list_it(repo: Path) -> None:
    entered(modes.enter(repo, "orient-only"))

    assert mode_hooks.operations(gateway(UNLISTED_READ), repo) is None


def test_a_mode_that_cannot_load_never_refuses_a_gateway_tool(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))
    (repo.parent / "modes" / "fixture" / "mode.toml").unlink()

    assert mode_hooks.operations(gateway(LISTED), repo) is None
    assert mode_hooks.operations(gateway(UNLISTED_WRITE), repo) is None
    assert mode_hooks.orient(repo) is None


def write_pointer(project: Path, how: str) -> None:
    """A hand-made pointer no work session backs, broken in the way `how` names."""
    path = state.mode_record(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    match how:
        case "invalid utf-8":
            path.write_bytes(b"\xff\xfe")
        case "invalid json":
            path.write_text("{damaged", encoding="utf-8")
        case "naive time":
            path.write_text(
                json.dumps(
                    {
                        "mode": "fixture",
                        "session_id": "WS-000000000000",
                        "root": "",
                        "entered": "2026-11-11T10:00:00",
                    }
                ),
                encoding="utf-8",
            )
        case "unknown mode":
            path.write_text(
                json.dumps(
                    {
                        "mode": "gone",
                        "session_id": "WS-000000000000",
                        "root": "",
                        "entered": "2026-11-11T10:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )


@pytest.mark.parametrize(
    "how", ["invalid utf-8", "invalid json", "naive time", "unknown mode"]
)
def test_a_pointer_nothing_backs_means_no_mode_and_no_call_is_denied(
    repo: Path, capsys: pytest.CaptureFixture[str], how: str
) -> None:
    write_pointer(repo, how)

    assert mode_hooks.orient(repo) is None
    assert mode_hooks.operations(gateway(UNLISTED_WRITE), repo) is None
    assert pre_tool_reason(repo, UNLISTED_READ, capsys) is None
    assert pre_tool_reason(repo, LISTED_READ, capsys) is None


def test_orient_shows_the_mode_once_a_broken_pointer_is_regenerated(
    repo: Path,
) -> None:
    entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    text = mode_hooks.orient(repo)

    assert text is not None
    assert text.startswith("[harness] mode: fixture. Rules:")


def test_a_paused_mode_session_is_resumed_and_its_operations_apply_again(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(work_sessions.transition(repo, active.session_id, "pause"), Ok)

    decision = mode_hooks.operations(gateway(UNLISTED_WRITE), repo)

    assert decision is not None
    assert decision.rule == "mode-operations"


# the hook path


def test_the_hook_refuses_an_unlisted_gateway_read_inside_the_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    reason = pre_tool_reason(repo, UNLISTED_READ, capsys)

    assert reason is not None
    assert "[harness mode-operations]" in reason


def test_review_focus_3_an_always_on_control_still_denies_inside_the_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    reason = pre_tool_reason(repo, LISTED, capsys)

    assert reason is not None
    assert "[harness approval-required]" in reason


def test_the_hook_allows_a_listed_gateway_read_inside_the_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    assert pre_tool_reason(repo, LISTED_READ, capsys) is None


def test_the_hook_does_not_scope_gateway_reads_outside_a_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert pre_tool_reason(repo, UNLISTED_READ, capsys) is None


# the conversation's session


def bound_to(project: Path, conversation: str) -> str | None:
    match work_session_context.resolve_session(project, "claude", conversation):
        case Ok(identifier):
            return identifier
        case failure:
            raise AssertionError(f"the conversation link cannot be read: {failure!r}")


def test_the_hook_binds_an_unbound_conversation_to_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert bound_to(repo, "chat-a") is None

    assert pre_tool_reason(repo, LISTED_READ, capsys, "chat-a") is None

    assert bound_to(repo, "chat-a") == active.session_id


def test_the_hook_asks_nothing_when_it_binds_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    pre_tool_reason(repo, LISTED_READ, capsys, "chat-a")

    assert not decisions.any_waiting(repo)


def test_a_conversation_already_bound_stays_in_its_own_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = work_sessions.create(repo, "other work")
    assert isinstance(other, Ok)
    assert isinstance(
        work_session_context.bind_session(repo, "claude", "chat-a", other.value.id),
        Ok,
    )
    entered(modes.enter(repo, "fixture"))

    pre_tool_reason(repo, LISTED_READ, capsys, "chat-a")

    assert bound_to(repo, "chat-a") == other.value.id


def test_a_conversation_that_left_a_mode_joins_the_next_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    pre_tool_reason(repo, LISTED_READ, capsys, "chat-a")
    assert isinstance(modes.leave(repo), Ok)
    second = entered(modes.enter(repo, "fixture"))

    assert pre_tool_reason(repo, LISTED_READ, capsys, "chat-a") is None
    assert bound_to(repo, "chat-a") == second.session_id
    hook.handle_prompt(
        "claude",
        {"cwd": str(repo), "prompt": "approve HB-ABCD1234", "session_id": "chat-a"},
    )
    capsys.readouterr()

    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None


def test_a_damaged_link_is_neither_replaced_nor_moved_by_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    link = work_session_context._path(repo, "claude", "chat-a")
    assert isinstance(link, Ok)
    link.value.parent.mkdir(parents=True, exist_ok=True)
    link.value.write_text("{damaged", encoding="utf-8")
    hook.handle_pre_tool(
        "claude",
        "pre-tool",
        {
            "cwd": str(repo),
            "tool_name": "Read",
            "tool_input": {"file_path": str(repo / "notes.txt")},
            "session_id": "chat-a",
        },
    )
    assert capsys.readouterr().out.strip() == ""

    assert link.value.read_text(encoding="utf-8") == "{damaged"
    assert not list(link.value.parent.glob("*.damaged-*.json"))


def pre_tool_output(
    project: Path,
    tool: str,
    capsys: pytest.CaptureFixture[str],
    conversation: str,
) -> str:
    """The raw text the hook prints for a gateway call."""
    hook.handle_pre_tool(
        "claude",
        "pre-tool",
        {
            "cwd": str(project),
            "tool_name": GATEWAY + tool,
            "tool_input": {},
            "session_id": conversation,
        },
    )
    return capsys.readouterr().out.strip()


# the controls a mode never touches


@pytest.mark.parametrize(
    "in_a_mode", [True, False], ids=["in a mode", "outside a mode"]
)
def test_harness_controls_still_act_from_the_users_prompt(
    repo: Path, in_a_mode: bool
) -> None:
    if in_a_mode:
        entered(modes.enter(repo, "fixture"))
    prompt = {"cwd": str(repo), "session_id": "chat-a"}

    hook.handle_prompt("claude", {**prompt, "prompt": "harness suspend"})
    assert state.harness_mode(repo) == "suspended"

    hook.handle_prompt("claude", {**prompt, "prompt": "harness resume"})
    assert state.harness_mode(repo) == "active"
