"""The mode hooks act only while a mode is active and its manifest lists them.

`orient` puts the mode's rules in the prompt's context; `operations` refuses a gateway tool the mode
does not list. The tests run in-process, with `modes.MODES_ROOT` pointed at fixture folders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.result import Err, Ok
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
RULES_UNREADABLE = (
    "The fixture mode's rules could not be read, so this prompt carries none of them."
)


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
    assert mode_hooks.orient(repo) == mode_hooks.Orientation()


def test_orient_gives_the_mode_and_its_rules_inside_one(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))

    oriented = mode_hooks.orient(repo)

    assert oriented.text is not None
    assert oriented.text.startswith("[harness] mode: fixture. Rules:")
    assert "# fixture" in oriented.text
    assert oriented.notice == ""


def test_orient_is_silent_when_the_manifest_does_not_list_it(repo: Path) -> None:
    entered(modes.enter(repo, "operations-only"))

    assert mode_hooks.orient(repo) == mode_hooks.Orientation()


def test_orient_says_when_the_mode_rules_cannot_be_read(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))
    (repo.parent / "modes" / "fixture" / "rules.md").write_bytes(b"\xff\xfe")

    oriented = mode_hooks.orient(repo)

    assert oriented.text is None
    assert oriented.notice == RULES_UNREADABLE


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
    assert RULES_UNREADABLE in out
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
    assert mode_hooks.orient(repo) == mode_hooks.Orientation()


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

    assert mode_hooks.orient(repo) == mode_hooks.Orientation()
    assert mode_hooks.operations(gateway(UNLISTED_WRITE), repo) is None
    assert pre_tool_reason(repo, UNLISTED_READ, capsys) is None
    assert pre_tool_reason(repo, LISTED_READ, capsys) is None


def test_orient_shows_the_mode_once_a_broken_pointer_is_regenerated(
    repo: Path,
) -> None:
    entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    oriented = mode_hooks.orient(repo)

    assert oriented.text is not None
    assert oriented.text.startswith("[harness] mode: fixture. Rules:")


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


# the conversation's session: derived on every call from the mode record, never stored

RECOVERED = "Recovered the fixture mode."
UNRECOVERED = (
    "The fixture mode could not be recovered; run `harness modes leave` to end it."
)
GENERIC_UNRECOVERED = (
    "A mode could not be recovered; run `harness modes leave` to end it."
)


def links(project: Path) -> dict[str, str]:
    """Every conversation-to-session link on disk, by file name."""
    folder = project / work_session_context.ROOT
    if not folder.exists():
        return {}
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(folder.rglob("*.json"))
    }


def acting(project: Path, conversation: str) -> str | None:
    """The work session the hook says this conversation acts in."""
    match work_session_context.for_payload(
        project, "claude", {"session_id": conversation}
    ):
        case Ok(identifier):
            return identifier
        case failure:
            raise AssertionError(
                f"the conversation's session is unreadable: {failure!r}"
            )


def approve(project: Path, conversation: str, approval: str = "HB-ABCD1234") -> None:
    hook.handle_prompt(
        "claude",
        {
            "cwd": str(project),
            "prompt": f"approve {approval}",
            "session_id": conversation,
        },
    )


def choose(project: Path, conversation: str, identifier: str) -> None:
    """The conversation explicitly selects a session, as `work-session select` does."""
    assert isinstance(
        work_session_context.bind_session(project, "claude", conversation, identifier),
        Ok,
    )


def started(project: Path, request: str = "other work") -> work_sessions.Session:
    created = work_sessions.create(project, request)
    assert isinstance(created, Ok)
    return created.value


def test_an_unbound_conversation_acts_in_the_mode_session_and_stores_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    before = links(repo)

    assert acting(repo, "chat-a") == active.session_id
    assert pre_tool_reason(repo, LISTED_READ, capsys, "chat-a") is None
    approve(repo, "chat-a")
    capsys.readouterr()

    assert state.open_approvals(repo, active.session_id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert links(repo) == before == {}


def test_a_host_that_names_no_conversation_acts_in_the_mode_session_too(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))

    match work_session_context.for_payload(repo, "claude", {}):
        case Ok(identifier):
            assert identifier == active.session_id
        case failure:
            raise AssertionError(f"unexpected {failure!r}")


def test_the_hook_asks_nothing_of_a_conversation_acting_in_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    pre_tool_reason(repo, LISTED_READ, capsys, "chat-a")

    assert not decisions.any_waiting(repo)


def test_leaving_and_entering_again_in_the_same_conversation_acts_in_the_new_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    pre_tool_reason(repo, LISTED_READ, capsys, "chat-a")
    assert isinstance(modes.leave(repo), Ok)
    second = entered(modes.enter(repo, "fixture"))

    assert acting(repo, "chat-a") == second.session_id
    approve(repo, "chat-a")
    capsys.readouterr()

    assert state.open_approvals(repo, second.session_id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert links(repo) == {}


def test_a_link_to_an_ended_session_counts_as_no_choice(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = started(repo)
    choose(repo, "chat-a", old.id)
    assert isinstance(work_sessions.transition(repo, old.id, "complete"), Ok)
    active = entered(modes.enter(repo, "fixture"))
    before = links(repo)

    assert acting(repo, "chat-a") == active.session_id
    approve(repo, "chat-a")
    capsys.readouterr()

    assert state.open_approvals(repo, active.session_id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert links(repo) == before


def test_a_conversation_that_chose_another_live_session_keeps_it_in_a_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = started(repo)
    choose(repo, "chat-a", other.id)
    active = entered(modes.enter(repo, "fixture"))
    before = links(repo)

    assert acting(repo, "chat-a") == other.id
    approve(repo, "chat-a")
    capsys.readouterr()

    assert state.open_approvals(repo, other.id)
    assert not state.open_approvals(repo, active.session_id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert links(repo) == before


def damage_link(project: Path, conversation: str) -> Path:
    link = work_session_context._path(project, "claude", conversation)
    assert isinstance(link, Ok)
    link.value.parent.mkdir(parents=True, exist_ok=True)
    link.value.write_text("{damaged", encoding="utf-8")
    return link.value


def test_a_damaged_link_is_still_refused_while_a_mode_is_active(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    link = damage_link(repo, "chat-a")

    reason = pre_tool_reason(repo, LISTED_READ, capsys, "chat-a")

    assert reason is not None
    assert "[harness work-session-context]" in reason
    assert isinstance(
        work_session_context.for_payload(repo, "claude", {"session_id": "chat-a"}),
        Err,
    )
    assert link.read_text(encoding="utf-8") == "{damaged"


def test_a_damaged_link_is_neither_replaced_nor_moved_by_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    link = damage_link(repo, "chat-a")
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

    assert link.read_text(encoding="utf-8") == "{damaged"
    assert not list(link.parent.glob("*.damaged-*.json"))


def pre_tool_output(
    project: Path,
    tool: str,
    capsys: pytest.CaptureFixture[str],
    conversation: str = "chat-a",
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


def notice_in(output: str) -> str:
    return json.loads(output)["hookSpecificOutput"]["additionalContext"]


# a mode that was repaired tells the agent, once; one that could not be repaired says so


def test_no_notice_while_the_mode_is_healthy(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    assert pre_tool_output(repo, LISTED_READ, capsys) == ""


def test_a_recovered_mode_tells_the_agent_once_and_allows_the_call(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    out = pre_tool_output(repo, LISTED_READ, capsys)

    assert notice_in(out) == RECOVERED
    assert active.session_id not in out
    assert "deny" not in out
    assert pre_tool_output(repo, LISTED_READ, capsys) == ""


def test_a_paused_mode_session_is_resumed_by_the_next_call_with_a_notice(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(work_sessions.transition(repo, active.session_id, "pause"), Ok)

    out = pre_tool_output(repo, LISTED_READ, capsys)

    assert notice_in(out) == RECOVERED
    assert active.session_id not in out
    assert acting(repo, "chat-a") == active.session_id


def test_a_completed_mode_session_is_replaced_and_the_conversation_acts_in_the_new_one(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture", root="EPIC-1"))
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)

    out = pre_tool_output(repo, LISTED_READ, capsys)

    assert notice_in(out) == RECOVERED
    assert active.session_id not in out
    new = acting(repo, "chat-a")
    assert new is not None and new != active.session_id
    assert links(repo) == {}
    approve(repo, "chat-a")
    capsys.readouterr()
    assert state.open_approvals(repo, new)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None


def test_an_approval_typed_when_the_mode_needs_recovery_lands_in_the_recovered_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)

    approve(repo, "chat-a")
    out = capsys.readouterr().out

    assert RECOVERED in out
    assert "approval HB-ABCD1234 recorded" in out
    assert active.session_id not in out
    new = acting(repo, "chat-a")
    assert new is not None and new != active.session_id
    assert state.open_approvals(repo, new)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None


def test_the_prompt_tells_the_agent_when_the_mode_was_recovered(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).unlink()

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )

    out = capsys.readouterr().out
    assert RECOVERED in out
    assert "[harness] mode: fixture. Rules:" in out
    assert active.session_id not in out


def test_the_prompt_after_a_broken_pointer_shows_the_mode_the_notice_and_keeps_the_file(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )

    out = capsys.readouterr().out
    assert RECOVERED in out
    assert "[harness] mode: fixture. Rules:" in out
    assert active.session_id not in out
    (kept,) = state.state_dir(repo).glob("mode.json.damaged-*")
    assert kept.read_bytes() == b"\xff\xfe"


def two_live_mode_sessions(repo: Path) -> modes.Active:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(work_sessions.create(repo, "other", mode="fixture"), Ok)
    state.mode_record(repo).unlink()
    return active


def test_a_mode_that_could_not_be_recovered_is_said_on_every_call_and_denies_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = two_live_mode_sessions(repo)

    for _ in range(2):
        out = pre_tool_output(repo, UNLISTED_READ, capsys)
        assert notice_in(out) == UNRECOVERED
        assert active.session_id not in out
        assert "deny" not in out
    reason = pre_tool_reason(repo, UNLISTED_WRITE, capsys, "chat-a")
    assert reason is not None
    assert "mode-operations" not in reason


def test_the_prompt_says_when_the_mode_could_not_be_recovered(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    two_live_mode_sessions(repo)

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )

    out = capsys.readouterr().out
    assert UNRECOVERED in out
    assert "[harness] mode:" not in out


def test_a_repair_that_fails_without_a_known_mode_is_still_said_on_the_call(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    def refuse(_: Path) -> None:
        raise OSError("cannot move the file")

    monkeypatch.setattr(modes, "_set_aside", refuse)

    out = pre_tool_output(repo, UNLISTED_READ, capsys)

    assert notice_in(out) == GENERIC_UNRECOVERED
    assert "deny" not in out


def test_leaving_ends_a_mode_that_could_not_be_recovered(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    two_live_mode_sessions(repo)
    assert pre_tool_output(repo, UNLISTED_READ, capsys) != ""

    assert isinstance(modes.leave(repo), Ok)

    assert pre_tool_output(repo, UNLISTED_READ, capsys) == ""


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
