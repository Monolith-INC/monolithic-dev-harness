"""The mode hooks act only while a mode is active and its manifest lists them.

`orient` puts the mode's rules in the prompt's context; `operations` refuses a gateway tool the mode
does not list. The tests run in-process, with `modes.MODES_ROOT` pointed at fixture folders.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import (
    cli,
    decisions,
    hook,
    mode_hooks,
    modes,
    questions,
    rules,
    settings,
    state,
    tracker_policy,
    work_sessions,
    workflow,
    workflow_evidence,
)
from host_adapters import hook_bridge, work_session_context
from integrations import gateway as integration_gateway
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


def state_files(project: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(project)): path.read_bytes()
        for path in sorted(state.state_dir(project).rglob("*"))
        if path.is_file() and path.name != "mode.lock"
    }


def test_the_hook_asks_and_stores_nothing_for_a_conversation_acting_in_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    before = state_files(repo)

    assert pre_tool_reason(repo, LISTED_READ, capsys, "chat-a") is None
    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )
    capsys.readouterr()

    assert not decisions.any_waiting(repo)
    assert state_files(repo) == before


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


def test_a_conversation_that_chose_another_live_session_after_the_mode_was_entered_keeps_it(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    other = started(repo)
    choose(repo, "chat-a", other.id)
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


def unrecoverable_mode(repo: Path, monkeypatch: pytest.MonkeyPatch) -> modes.Active:
    """A mode whose pointer is gone and cannot be written back: every call fails to repair it."""
    active = entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).unlink()
    write_json = state.write_json

    def refuse(path: Path, payload: dict) -> None:
        if path == state.mode_record(repo):
            raise OSError("the pointer cannot be written")
        write_json(path, payload)

    monkeypatch.setattr(state, "write_json", refuse)
    return active


def test_a_mode_that_could_not_be_recovered_is_said_on_every_call_and_denies_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    active = unrecoverable_mode(repo, monkeypatch)

    for _ in range(2):
        out = pre_tool_output(repo, UNLISTED_READ, capsys)
        assert notice_in(out) == UNRECOVERED
        assert active.session_id not in out
        assert "deny" not in out
    reason = pre_tool_reason(repo, UNLISTED_WRITE, capsys, "chat-a")
    assert reason is not None
    assert "mode-operations" not in reason


def test_the_prompt_says_when_the_mode_could_not_be_recovered(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    unrecoverable_mode(repo, monkeypatch)

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
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    unrecoverable_mode(repo, monkeypatch)
    assert pre_tool_output(repo, UNLISTED_READ, capsys) != ""

    assert isinstance(modes.leave(repo), Ok)

    assert pre_tool_output(repo, UNLISTED_READ, capsys) == ""


# an approval belongs to the content it approves: a replaced mode session does not lose it

DRAFT = "drafts/vision.md"
APPROVED_BODY = "# Vision\n\nThe approved text.\n"


def draft_digest(project: Path) -> str:
    match workflow.file_digest(project / DRAFT):
        case Ok(digest):
            return digest
        case failure:
            raise AssertionError(f"cannot read the draft: {failure!r}")


def reviewed_draft(project: Path) -> dict:
    """What the user reviewed: the draft file and the body it holds."""
    path = project / DRAFT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(APPROVED_BODY, encoding="utf-8")
    return {
        "artifacts": [[DRAFT, draft_digest(project)]],
        "bodies": [hashlib.sha256(APPROVED_BODY.strip().encode()).hexdigest()],
    }


def approve_content(project: Path, session: str | None) -> None:
    state.open_approval(
        project,
        "HB-CONTENT1",
        20,
        work_session_id=session,
        binds=reviewed_draft(project),
    )


def body_decision(project: Path, session: str | None, body: str) -> rules.Decision:
    call = rules.make_call(
        "tracker_update_work_item",
        {"description": body},
        "plugin_monolithic-dev-harness_workflow-integrations",
        kind="mcp",
    )
    loaded = settings.load(project)
    return rules.rule_approval_required(
        call, project, tracker_policy.build(project, loaded), session
    )


def test_an_approval_of_reviewed_content_survives_the_mode_session_being_replaced(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approve_content(repo, active.session_id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)

    still_approved = pre_tool_reason(repo, LISTED, capsys, "chat-a")

    new = acting(repo, "chat-a")
    assert new is not None and new != active.session_id
    assert still_approved is None


def test_content_that_changed_after_it_was_approved_is_still_refused_in_a_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approve_content(repo, active.session_id)
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)
    (repo / DRAFT).write_text(APPROVED_BODY + "an edit nobody approved\n")

    reason = pre_tool_reason(repo, LISTED, capsys, "chat-a")

    assert reason is not None
    assert "[harness approval-required]" in reason
    assert "changed" in reason


def test_an_approved_body_is_held_to_in_a_mode_whichever_session_is_running(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approve_content(repo, active.session_id)
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)
    new = modes.active(repo)
    assert new is not None and new.session_id != active.session_id

    assert body_decision(repo, new.session_id, APPROVED_BODY).allowed
    different = body_decision(repo, new.session_id, APPROVED_BODY + "more")
    assert not different.allowed
    assert "no approved draft holds" in (different.reason or "")


# the receipt of a publication, and a question answered about the same content, follow the content


PUBLISH_ANSWER = "publish"
DOCUMENT_QUESTION = "Approve this document and save it?"
DOCUMENT_OPTIONS = ("Approve", "Not now")


def approved_publication(project: Path, session: str) -> str:
    """The user approved publishing in this session: its answer, and the approval that answer opened,
    tied to the reviewed draft. Returns the approval's id."""
    folder = work_sessions.select(project, session).value.folder
    approval = questions.approval_id(PUBLISH_ANSWER)
    state.write_json(
        folder / decisions.HISTORY,
        {
            "answers": [
                {
                    "id": PUBLISH_ANSWER,
                    "gate": "publish-items",
                    "status": "answered",
                    "answer": "Approve (Recommended)",
                }
            ]
        },
    )
    state.open_approval(
        project, approval, 20, work_session_id=session, binds=reviewed_draft(project)
    )
    return approval


def create_item(project: Path) -> None:
    created = integration_gateway.handle_call(
        "tracker_create_work_item",
        {"kind": "epic", "title": "Discovery Epic"},
        project,
    )
    assert isinstance(created, Ok), created


def receipts(project: Path, session: str) -> tuple[dict, ...]:
    return workflow_evidence.publications(work_sessions.select(project, session).value)


def replaced(project: Path, session: str) -> str:
    """The mode's session ended: the next read of the mode replaces it. Returns the new one."""
    assert isinstance(work_sessions.transition(project, session, "complete"), Ok)
    successor = modes.active(project)
    assert successor is not None and successor.session_id != session
    return successor.session_id


def test_a_publication_receipt_is_recorded_in_the_mode_session_that_was_approved(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approval = approved_publication(repo, active.session_id)

    create_item(repo)

    (receipt,) = receipts(repo, active.session_id)
    assert receipt["approval_id"] == approval


def test_a_publication_receipt_finds_the_approval_given_before_the_mode_session_was_replaced(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approval = approved_publication(repo, active.session_id)
    new = replaced(repo, active.session_id)

    create_item(repo)

    (receipt,) = receipts(repo, new)
    assert receipt["approval_id"] == approval
    assert receipt["work_session"] == new


def test_outside_a_mode_a_publication_receipt_never_borrows_an_approval_of_an_ended_session(
    repo: Path,
) -> None:
    ended = started(repo, "work that ended")
    approved_publication(repo, ended.id)
    assert isinstance(work_sessions.transition(repo, ended.id, "complete"), Ok)
    successor = started(repo, "work that went on")

    create_item(repo)

    assert receipts(repo, successor.id) == ()


def test_a_publication_with_no_approval_anywhere_leaves_no_receipt_in_a_mode(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    new = replaced(repo, active.session_id)

    create_item(repo)

    assert receipts(repo, new) == ()


def answered_document(project: Path, session: str) -> tuple[str, tuple]:
    """The user approved this draft in this session. Returns the answer's id and the draft as asked."""
    folder = work_sessions.select(project, session).value.folder
    artifacts = ((DRAFT, draft_digest(project)),)
    answer = "answer-document"
    state.write_json(
        folder / decisions.HISTORY,
        {
            "answers": [
                {
                    "id": PUBLISH_ANSWER,
                    "gate": "approve-document",
                    "status": "answered",
                    "answer": "Approve",
                    "question": DOCUMENT_QUESTION,
                    "options": list(DOCUMENT_OPTIONS),
                    "approval": True,
                    "artifacts": [list(pair) for pair in artifacts],
                }
            ]
        },
    )
    state.open_approval(
        project,
        questions.approval_id(answer),
        20,
        work_session_id=session,
        binds={"artifacts": [list(pair) for pair in artifacts]},
    )
    return answer, artifacts


def asked_again(project: Path, session: str, artifacts: tuple) -> dict | None:
    return decisions.reusable(
        project,
        DOCUMENT_QUESTION,
        DOCUMENT_OPTIONS,
        artifacts,
        True,
        work_session_id=session,
    )


def test_a_question_answered_about_the_same_content_is_not_asked_again_once_the_mode_session_was_replaced(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    reviewed_draft(repo)
    answer, artifacts = answered_document(repo, active.session_id)
    new = replaced(repo, active.session_id)

    reused = asked_again(repo, new, artifacts)

    assert reused is not None and reused["id"] == answer


def test_a_question_about_content_that_changed_is_asked_again_in_a_mode(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    reviewed_draft(repo)
    _, artifacts = answered_document(repo, active.session_id)
    new = replaced(repo, active.session_id)
    (repo / DRAFT).write_text(APPROVED_BODY + "an edit nobody approved\n")

    assert asked_again(repo, new, ((DRAFT, draft_digest(repo)),)) is None


def test_a_question_answered_in_an_ended_mode_session_is_asked_again_once_the_mode_is_left(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    reviewed_draft(repo)
    _, artifacts = answered_document(repo, active.session_id)
    assert isinstance(modes.leave(repo), Ok)
    fresh = started(repo, "work after the mode")

    assert asked_again(repo, fresh.id, artifacts) is None


def test_outside_a_mode_an_answer_of_another_session_is_never_reused(
    repo: Path,
) -> None:
    ended = started(repo, "work that ended")
    reviewed_draft(repo)
    _, artifacts = answered_document(repo, ended.id)
    assert isinstance(work_sessions.transition(repo, ended.id, "complete"), Ok)
    successor = started(repo, "work that went on")

    assert asked_again(repo, successor.id, artifacts) is None


def test_a_general_window_is_still_its_own_sessions_inside_a_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approve(repo, "chat-a")
    capsys.readouterr()
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)

    reason = pre_tool_reason(repo, LISTED, capsys, "chat-a")

    assert reason is not None
    assert "[harness approval-required]" in reason


def test_an_approval_typed_in_a_mode_is_the_mode_sessions_and_not_project_wide(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))

    approve(repo, "chat-a")
    capsys.readouterr()

    ((_, record),) = state.open_approvals(repo, active.session_id)
    assert record["work_session"] == active.session_id
    assert state.open_approvals(repo, None) == []


def test_an_approval_of_reviewed_content_covers_nothing_once_the_mode_is_left(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    approve_content(repo, active.session_id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert isinstance(modes.leave(repo), Ok)

    reason = pre_tool_reason(repo, LISTED, capsys, "chat-a")

    assert reason is not None
    assert "[harness approval-required]" in reason


def test_outside_a_mode_an_approval_stays_with_the_session_it_was_given_in(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = move_current_elsewhere(repo)
    choose(repo, "chat-a", mine.id)
    approve_content(repo, mine.id)
    assert pre_tool_reason(repo, LISTED, capsys, "chat-a") is None
    assert isinstance(work_sessions.transition(repo, mine.id, "complete"), Ok)
    successor = move_current_elsewhere(repo)
    choose(repo, "chat-a", successor.id)

    reason = pre_tool_reason(repo, LISTED, capsys, "chat-a")

    assert reason is not None
    assert "[harness approval-required]" in reason


def test_an_approval_of_another_session_does_not_cover_a_conversation_outside_a_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = move_current_elsewhere(repo)
    other = started(repo, "another conversation's work")
    choose(repo, "chat-a", mine.id)
    approve_content(repo, other.id)

    reason = pre_tool_reason(repo, LISTED, capsys, "chat-a")

    assert reason is not None
    assert "[harness approval-required]" in reason


# a conversation in a mode acts in the mode's session, so its commands do, and no message names it

CLI = Path(hook.PLUGIN_ROOT) / "bin" / "harness"


def shell_output(
    project: Path,
    command: str,
    capsys: pytest.CaptureFixture[str],
    conversation: str = "chat-a",
) -> str:
    """The raw text the hook prints for a shell command."""
    hook.handle_pre_tool(
        "claude",
        "pre-tool",
        {
            "cwd": str(project),
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "session_id": conversation,
        },
    )
    return capsys.readouterr().out


def move_current_elsewhere(project: Path) -> work_sessions.Session:
    """Another conversation's `begin`: it starts a session and makes it the project's current one."""
    started_elsewhere = work_sessions.start(project, "somebody else's work")
    assert isinstance(started_elsewhere, Ok)
    return started_elsewhere.value


def ids_in(text: str, *known: str) -> list[str]:
    return [identifier for identifier in known if identifier in text] + (
        ["a work-session id"] if "WS-" in text else []
    )


def test_an_implied_command_in_a_mode_is_not_refused_because_current_points_elsewhere(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    other = move_current_elsewhere(repo)
    assert work_sessions.current(repo) == other.id
    implied = (
        f"{CLI} decision present --repo {repo} --gate publish-branch --value branch=x"
    )

    out = shell_output(repo, implied, capsys)

    assert "work-session-mismatch" not in out
    assert ids_in(out, active.session_id, other.id) == []


def test_a_command_naming_another_session_in_a_mode_is_refused_without_naming_any(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    other = move_current_elsewhere(repo)
    named = (
        f"{CLI} decision present --repo {repo} --gate publish-branch "
        f"--value branch=x --session-id {other.id}"
    )

    out = shell_output(repo, named, capsys)

    assert "work-session-mismatch" in out
    assert "fixture" in out
    assert ids_in(out, active.session_id, other.id) == []


def test_outside_a_mode_the_mismatch_still_names_both_sessions(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = move_current_elsewhere(repo)
    other = work_sessions.create(repo, "other work")
    assert isinstance(other, Ok)
    choose(repo, "chat-a", mine.id)
    implied_elsewhere = work_sessions.start(repo, "third")
    assert isinstance(implied_elsewhere, Ok)
    implied = (
        f"{CLI} decision present --repo {repo} --gate publish-branch --value branch=x"
    )

    out = shell_output(repo, implied, capsys)

    assert "work-session-mismatch" in out
    assert mine.id in out and implied_elsewhere.value.id in out


# a harness command that names no session acts in the mode's session, wherever `current` points


def present_gate(project: Path, *extra: str) -> int:
    return cli.main(
        ["decision", "present", "--gate", "planning-depth", "--host", "text"]
        + ["--repo", str(project), *extra]
    )


# the newest explicit choice wins: entering a mode is a conversation's newest choice, unless it
# chose a session again while the mode ran. The hook and the CLI give the same answer.


def present_command(project: Path, *extra: str) -> str:
    """The shell command `present_gate` runs, as the agent would type it."""
    return (
        f"{CLI} decision present --gate planning-depth --host text --repo {project} "
        + " ".join(extra)
    ).strip()


def asked_in(project: Path, *sessions: str) -> list[str]:
    """The sessions among these that hold a pending question."""
    return [
        identifier
        for identifier in sessions
        if decisions.pending(project, identifier) is not None
    ]


def test_a_conversation_bound_before_the_mode_was_entered_acts_in_the_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = started(repo)
    choose(repo, "chat-a", other.id)
    active = entered(modes.enter(repo, "fixture"))

    assert acting(repo, "chat-a") == active.session_id
    assert shell_output(repo, present_command(repo), capsys) == ""
    assert present_gate(repo) == 0
    capsys.readouterr()
    assert asked_in(repo, active.session_id, other.id) == [active.session_id]


def test_the_reply_to_a_question_the_mode_asked_is_seen_by_a_conversation_bound_before_it(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = started(repo)
    choose(repo, "chat-a", other.id)
    active = entered(modes.enter(repo, "fixture"))
    assert present_gate(repo) == 0
    capsys.readouterr()

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "1", "session_id": "chat-a"}
    )

    assert "human decision recorded" in capsys.readouterr().out
    answered = decisions.record(repo, active.session_id)
    assert answered is not None and answered["status"] == "answered"
    assert asked_in(repo, active.session_id, other.id) == []


def test_a_conversation_returns_to_the_session_it_chose_once_the_mode_is_left(
    repo: Path,
) -> None:
    other = started(repo)
    choose(repo, "chat-a", other.id)
    entered(modes.enter(repo, "fixture"))
    assert isinstance(modes.leave(repo), Ok)

    assert acting(repo, "chat-a") == other.id


def test_a_session_chosen_while_the_mode_runs_wins_over_the_mode(
    repo: Path,
) -> None:
    other = started(repo)
    choose(repo, "chat-a", other.id)
    entered(modes.enter(repo, "fixture"))
    chosen_again = started(repo, "chosen during the mode")
    choose(repo, "chat-a", chosen_again.id)

    assert acting(repo, "chat-a") == chosen_again.id


@pytest.mark.parametrize(
    ("scenario", "allowed"),
    [
        ("unbound", True),
        ("bound-before-the-mode", True),
        ("bound-after-the-mode", False),
    ],
)
def test_the_hook_allows_a_command_without_a_session_only_where_the_cli_runs_it_in_the_conversations_session(
    scenario: str, allowed: bool, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = started(repo, "other work")
    if scenario == "bound-before-the-mode":
        choose(repo, "chat-a", other.id)
    active = entered(modes.enter(repo, "fixture"))
    if scenario == "bound-after-the-mode":
        choose(repo, "chat-a", other.id)
    acts_in = acting(repo, "chat-a")

    out = shell_output(repo, present_command(repo), capsys)

    assert (out == "") is allowed, out
    if allowed:
        assert present_gate(repo) == 0
        capsys.readouterr()
        assert asked_in(repo, active.session_id, other.id) == [acts_in]


def test_a_command_without_a_session_from_a_conversation_outside_the_mode_is_refused_by_name_of_its_own(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    mine = work_sessions.start(repo, "story work").value
    choose(repo, "chat-b", mine.id)
    assert work_sessions.current(repo) == mine.id

    out = shell_output(repo, present_command(repo), capsys, "chat-b")

    assert "work-session-mismatch" in out
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert f"--session-id {mine.id}" in reason
    assert "fixture" in reason
    assert active.session_id not in reason
    assert asked_in(repo, active.session_id, mine.id) == []


def test_a_conversation_bound_after_the_mode_was_entered_works_in_its_own_session_with_its_id(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    mine = work_sessions.start(repo, "story work").value
    choose(repo, "chat-b", mine.id)
    named = present_command(repo, "--session-id", mine.id)

    assert shell_output(repo, named, capsys, "chat-b") == ""
    assert present_gate(repo, "--session-id", mine.id) == 0
    capsys.readouterr()

    assert asked_in(repo, active.session_id, mine.id) == [mine.id]


def test_decision_present_in_a_mode_records_the_decision_in_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    other = move_current_elsewhere(repo)
    assert work_sessions.current(repo) == other.id

    assert present_gate(repo) == 0

    asked = decisions.pending(repo, active.session_id)
    assert asked is not None
    assert asked.scope == active.session_id
    assert decisions.pending(repo, other.id) is None
    capsys.readouterr()


def test_outside_a_mode_decision_present_still_records_in_the_current_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = move_current_elsewhere(repo)

    assert present_gate(repo) == 0

    asked = decisions.pending(repo, mine.id)
    assert asked is not None and asked.scope == mine.id
    capsys.readouterr()


def test_a_session_named_on_the_command_wins_over_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    other = move_current_elsewhere(repo)

    assert present_gate(repo, "--session-id", other.id) == 0

    asked = decisions.pending(repo, other.id)
    assert asked is not None and asked.scope == other.id
    assert decisions.pending(repo, active.session_id) is None
    capsys.readouterr()


def test_showing_a_file_in_a_mode_is_recorded_for_the_mode_session(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    other = move_current_elsewhere(repo)
    reviewed_draft(repo)

    shown = cli.main(["workflow", "show", "--artifact", DRAFT, "--repo", str(repo)])

    assert shown == 0
    session = work_sessions.select(repo, active.session_id).value
    assert (session.folder / "shown-artifacts.json").is_file()
    assert not (other_folder(repo, other.id) / "shown-artifacts.json").exists()
    capsys.readouterr()


def other_folder(project: Path, identifier: str) -> Path:
    return work_sessions.select(project, identifier).value.folder


def test_a_pending_decision_in_a_mode_is_guided_without_naming_the_session_or_the_decision(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(
        decisions.begin(
            repo,
            "d-private-1",
            "Continue?",
            ("Continue", "Stop"),
            "chat",
            work_session_id=active.session_id,
        ),
        Ok,
    )

    out = shell_output(repo, "touch notes.txt", capsys)

    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "decision-pending" in reason
    assert "fixture" in reason
    assert "decision fallback" in reason
    assert "--session-id" not in reason
    assert "d-private-1" not in reason
    assert ids_in(reason, active.session_id) == []


def test_a_pending_decision_outside_a_mode_still_names_the_session_and_the_decision(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = move_current_elsewhere(repo)
    assert isinstance(
        decisions.begin(
            repo,
            "d-private-1",
            "Continue?",
            ("Continue", "Stop"),
            "chat",
            work_session_id=mine.id,
        ),
        Ok,
    )

    reason = json.loads(shell_output(repo, "touch notes.txt", capsys))[
        "hookSpecificOutput"
    ]["permissionDecisionReason"]

    assert "d-private-1" in reason
    assert f"--session-id {mine.id}" in reason


# what the USER is shown: the host's own line, beside the context only the agent reads


def user_line(output: str) -> str | None:
    """The line the host shows the user (`systemMessage`), or None when the output has none."""
    return json.loads(output).get("systemMessage")


def damage(project: Path) -> None:
    state.mode_record(project).write_bytes(b"\xff\xfe")


def test_a_recovered_mode_is_shown_to_the_user_and_given_to_the_agent(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    damage(repo)

    out = pre_tool_output(repo, LISTED_READ, capsys)

    assert user_line(out) == RECOVERED
    assert notice_in(out) == RECOVERED
    assert active.session_id not in out
    assert pre_tool_output(repo, LISTED_READ, capsys) == ""


def test_a_denied_call_that_repaired_the_mode_still_tells_the_user(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    out = pre_tool_output(repo, UNLISTED_READ, capsys)

    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "[harness mode-operations]" in decision["permissionDecisionReason"]
    assert user_line(out) == RECOVERED
    assert pre_tool_output(repo, UNLISTED_READ, capsys) != ""
    assert "systemMessage" not in json.loads(
        pre_tool_output(repo, UNLISTED_READ, capsys)
    )


def test_a_mode_that_could_not_be_recovered_is_not_shown_to_the_user_on_every_call(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    unrecoverable_mode(repo, monkeypatch)

    for _ in range(2):
        out = pre_tool_output(repo, UNLISTED_READ, capsys)
        assert notice_in(out) == UNRECOVERED
        assert user_line(out) is None


def test_the_prompt_shows_the_user_the_repair_and_leaves_the_rest_to_the_agent(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    approve(repo, "chat-a")

    out = json.loads(capsys.readouterr().out)
    context = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert out["systemMessage"] == RECOVERED
    assert RECOVERED in context
    assert "approval HB-ABCD1234 recorded" in context
    assert "[harness] mode: fixture. Rules:" in context


def test_the_prompt_shows_the_user_a_mode_that_could_not_be_recovered(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    unrecoverable_mode(repo, monkeypatch)

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )

    out = json.loads(capsys.readouterr().out)
    assert out["systemMessage"] == UNRECOVERED
    assert UNRECOVERED in out["hookSpecificOutput"]["additionalContext"]


def test_the_prompt_shows_the_user_when_the_mode_rules_cannot_be_given(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    (repo.parent / "modes" / "fixture" / "rules.md").write_bytes(b"\xff\xfe")

    approve(repo, "chat-a")

    out = json.loads(capsys.readouterr().out)
    assert out["systemMessage"] == RULES_UNREADABLE
    assert (
        "approval HB-ABCD1234 recorded"
        in out["hookSpecificOutput"]["additionalContext"]
    )
    assert "approval" not in out["systemMessage"]


def test_a_healthy_mode_leaves_the_prompt_as_plain_text_for_claude(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    hook.handle_prompt(
        "claude", {"cwd": str(repo), "prompt": "what next?", "session_id": "chat-a"}
    )

    out = capsys.readouterr().out
    assert out.startswith("[harness] mode: fixture. Rules:")


def test_a_repair_found_first_by_a_stop_is_shown_to_the_user(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    hook.handle_stop(
        "claude",
        {"cwd": str(repo), "session_id": "chat-a", "last_assistant_message": "done"},
    )

    assert user_line(capsys.readouterr().out) == RECOVERED


def test_a_repair_found_first_by_an_answer_event_is_shown_to_the_user(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    hook.handle_answer("claude", {"cwd": str(repo), "session_id": "chat-a"})

    assert user_line(capsys.readouterr().out) == RECOVERED


def test_a_repair_found_first_by_a_question_is_shown_to_the_user_beside_its_verdict(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    hook.handle_ask(
        "claude",
        {
            "cwd": str(repo),
            "session_id": "chat-a",
            "tool_name": "AskUserQuestion",
            "tool_input": {"questions": []},
        },
    )

    out = capsys.readouterr().out
    assert user_line(out) == RECOVERED


def test_a_stop_after_a_healthy_read_says_nothing_to_the_user(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))

    hook.handle_stop(
        "claude",
        {"cwd": str(repo), "session_id": "chat-a", "last_assistant_message": "done"},
    )

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_the_hosts_with_a_user_channel_get_the_system_message(host: str) -> None:
    assert hook_bridge.reaches_user(host)
    assert (
        json.loads(hook_bridge.format_prompt(host, ["a"], ["b"]))["systemMessage"]
        == "b"
    )
    assert (
        json.loads(hook_bridge.format_pre_tool_notice("a", "b"))["systemMessage"] == "b"
    )


@pytest.mark.parametrize("host", ["cursor", "kimi", "zed"])
def test_the_hosts_with_no_user_channel_are_given_none(host: str) -> None:
    assert not hook_bridge.reaches_user(host)
    shown = hook_bridge.format_prompt(host, ["a"], ["b"])
    assert "systemMessage" not in (shown or "")


def test_codex_is_shown_the_repair_on_a_pre_tool_call_too(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    hook.handle_pre_tool(
        "codex",
        "pre-tool",
        {
            "cwd": str(repo),
            "tool_name": GATEWAY + UNLISTED_READ,
            "tool_input": {},
            "session_id": "chat-a",
        },
    )

    assert user_line(capsys.readouterr().out) == RECOVERED


def test_a_host_with_no_user_channel_keeps_its_own_output_on_a_repair(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    damage(repo)

    hook.handle_pre_tool(
        "cursor",
        "pre-tool",
        {
            "cwd": str(repo),
            "tool_name": "MCP:" + GATEWAY + LISTED_READ,
            "tool_input": {},
            "conversation_id": "chat-a",
        },
    )

    out = json.loads(capsys.readouterr().out)
    assert "systemMessage" not in out


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
