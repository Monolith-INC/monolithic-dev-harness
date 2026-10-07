"""Trusted host events connect successful startup to the next human question and answer."""

import json
import shlex
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, state, work_sessions
from host_adapters import startup_context, work_session_context
from tests.harness.test_discovery_render import cli, prepare, session
from tests.harness.test_hook_security import run_hook

HARNESS = str(Path(__file__).resolve().parents[2] / "bin/harness")


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    return prepare(tmp_path / "project")


def payload(command, call_id="begin-1", response=None):
    return {
        "session_id": "conversation",
        "tool_name": "Bash",
        "tool_use_id": call_id,
        "tool_input": {"command": command},
        "tool_response": response,
    }


def command(repo, request, extra=()):
    return shlex.join(
        (HARNESS, "begin", "--request", request, *extra, "--repo", str(repo))
    )


def response(host, result):
    match host:
        case "codex":
            return json.dumps({"exit_code": 0, "output": result.stdout})
        case _:
            return {"stdout": result.stdout, "stderr": "", "interrupted": False}


@pytest.mark.parametrize("host", ("codex", "claude"))
@pytest.mark.parametrize("selection", ("existing", "new", "fresh"))
def test_startup_binds_after_success_then_captures_the_selected_session_answer(
    project, host, selection
):
    first = session(project, "First work")
    assert work_session_context.bind_session(
        project, host, "conversation", first.id
    ) == Ok(first.id)
    selected = work_sessions.start(project, "Selected work").value
    extra = {"existing": ("--session", selected.id), "new": ("--new",), "fresh": ()}[
        selection
    ]
    request = {
        "existing": selected.request,
        "new": "New work",
        "fresh": selected.request,
    }[selection]
    cmd = command(project, request, extra)
    assert "deny" not in run_hook(project, "pre-tool", payload(cmd), host)
    assert work_session_context.resolve_session(project, host, "conversation") == Ok(
        first.id
    )
    result = cli(project, "begin", "--request", request, *extra)
    assert result.returncode == 0, result.stderr
    identifier = json.loads(result.stdout)["session_id"]
    assert "not confirmed" not in run_hook(
        project, "startup", payload(cmd, response=response(host, result)), host
    )
    assert work_session_context.resolve_session(project, host, "conversation") == Ok(
        identifier
    )
    question = {
        "questions": [
            {
                "id": "review",
                "header": "Review",
                "question": "Use this plan?",
                "options": [
                    {"label": "Continue", "description": "Keep this plan."},
                    {"label": "Revise", "description": "Change it."},
                ],
            }
        ]
    }
    question_payload = {
        "session_id": "conversation",
        "tool_use_id": "native-question",
        "tool_name": {"codex": "request_user_input", "claude": "AskUserQuestion"}[host],
        "tool_input": question,
    }
    assert "deny" not in run_hook(project, "ask", question_payload, host)
    assert decisions.pending(project, identifier).id == "native-question"
    answer = {
        "codex": {"answers": {"review": {"answers": ["Continue"]}}},
        "claude": {"answers": {"Use this plan?": "Continue"}},
    }[host]
    run_hook(project, "answer", {**question_payload, "tool_response": answer}, host)
    assert decisions.record(project, identifier)["answer"] == "Continue"
    assert decisions.record(project, first.id) is None


def test_pending_question_prevents_arming_a_switch(project):
    first = session(project)
    selected = work_sessions.start(project, "Other work").value
    work_session_context.bind_session(project, "codex", "conversation", first.id)
    decisions.begin(
        project,
        "pending",
        "Keep this plan?",
        ("Continue", "Revise"),
        "chat",
        work_session_id=first.id,
    )
    cmd = command(project, selected.request, ("--session", selected.id))
    assert "decision-pending" in run_hook(project, "pre-tool", payload(cmd))
    assert (
        state.read_json(startup_context._arm_path(project, "codex", "conversation"))
        is None
    )
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        first.id
    )


def test_failed_begin_does_not_switch_conversation(project):
    first = session(project)
    work_session_context.bind_session(project, "codex", "conversation", first.id)
    cmd = command(project, "Other work", ("--session", "WS-missing"))
    assert "deny" not in run_hook(project, "pre-tool", payload(cmd))
    result = cli(project, "begin", "--request", "Other work", "--session", "WS-missing")
    assert result.returncode != 0
    run_hook(
        project,
        "startup",
        payload(
            cmd, response={"exit_code": result.returncode, "output": result.stdout}
        ),
    )
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        first.id
    )


def test_unarmed_output_and_replay_cannot_switch_the_conversation(project):
    first = session(project)
    selected = work_sessions.start(project, "Other work").value
    work_session_context.bind_session(project, "codex", "conversation", first.id)
    cmd = command(project, selected.request, ("--session", selected.id))
    result = cli(
        project, "begin", "--request", selected.request, "--session", selected.id
    )
    completed = payload(cmd, response=response("codex", result))
    run_hook(project, "startup", completed)
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        first.id
    )
    run_hook(project, "pre-tool", payload(cmd))
    assert "not confirmed" in run_hook(
        project, "startup", completed
    )  # receipt predates arm
    result = cli(
        project, "begin", "--request", selected.request, "--session", selected.id
    )
    completed = payload(cmd, response=response("codex", result))
    run_hook(project, "startup", completed)
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        selected.id
    )
    work_session_context.bind_session(project, "codex", "conversation", first.id)
    run_hook(project, "startup", completed)
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        first.id
    )


def test_shell_operator_and_wrong_tool_id_do_not_bind(project):
    selected = session(project)
    cmd = command(project, selected.request)
    assert startup_context.invocation(cmd + " && touch extra", project) is None
    run_hook(project, "pre-tool", payload(cmd))
    result = cli(project, "begin", "--request", selected.request)
    run_hook(
        project,
        "startup",
        payload(cmd, call_id="other-call", response=response("codex", result)),
    )
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        None
    )


def test_setup_choice_is_not_a_successful_binding(tmp_path):
    cmd = command(tmp_path, "Work needing setup")
    run_hook(tmp_path, "pre-tool", payload(cmd))
    result = cli(tmp_path, "begin", "--request", "Work needing setup")
    assert json.loads(result.stdout)["state"] == "setup_needed"
    run_hook(tmp_path, "startup", payload(cmd, response=response("codex", result)))
    assert work_session_context.resolve_session(
        tmp_path, "codex", "conversation"
    ) == Ok(None)


@pytest.mark.parametrize("tool_name", ("exec_command", "functions.exec_command"))
def test_executor_payload_aliases_are_bound(project, tool_name):
    selected = session(project)
    cmd = command(project, selected.request)
    pre = {**payload(cmd), "tool_name": tool_name, "tool_input": {"cmd": cmd}}
    assert "deny" not in run_hook(project, "pre-tool", pre)
    result = cli(project, "begin", "--request", selected.request)
    run_hook(project, "startup", {**pre, "tool_response": response("codex", result)})
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        selected.id
    )
    import re

    config = json.loads(
        (Path(HARNESS).parents[1] / "hooks/codex.hooks.json").read_text()
    )
    assert re.fullmatch(config["hooks"]["PostToolUse"][-1]["matcher"], tool_name)
    assert re.search(config["hooks"]["PreToolUse"][0]["matcher"], tool_name)


def test_binding_write_failure_is_reported_and_retryable(project, monkeypatch, capsys):
    from core.result import err
    from harness import hook

    first = session(project)
    selected = work_sessions.start(project, "Selected work").value
    work_session_context.bind_session(project, "codex", "conversation", first.id)
    cmd = command(project, selected.request, ("--session", selected.id))
    run_hook(project, "pre-tool", payload(cmd))
    result = cli(
        project, "begin", "--request", selected.request, "--session", selected.id
    )
    completed = {
        "cwd": str(project),
        **payload(cmd, response=response("codex", result)),
    }
    with monkeypatch.context() as fault:
        fault.setattr(
            work_session_context,
            "bind_session",
            lambda *_args, **_kwargs: err("storage", "binding unavailable"),
        )
        assert hook.handle_startup("codex", completed) == 0
        assert "not confirmed" in capsys.readouterr().out
        assert work_session_context.resolve_session(
            project, "codex", "conversation"
        ) == Ok(first.id)
    assert hook.handle_startup("codex", completed) == 0
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        selected.id
    )


def test_missing_tool_identity_denies_begin_without_switching(project):
    selected = session(project)
    cmd = command(project, selected.request)
    assert "deny" in run_hook(project, "pre-tool", {**payload(cmd), "tool_use_id": ""})
    assert work_session_context.resolve_session(project, "codex", "conversation") == Ok(
        None
    )


def test_agents_cannot_execute_the_startup_host_handler(project):
    from harness import rules

    cmd = "python3 -c 'from host_adapters import startup_context; startup_context.complete()'"
    assert rules.runs_harness_hook(cmd)
    assert "hook-entry" in run_hook(project, "pre-tool", payload(cmd))


@pytest.mark.parametrize("host", ("codex", "claude"))
def test_cleanup_failure_cannot_rebind_a_consumed_startup(project, monkeypatch, host):
    from core.result import Err

    selected = session(project)
    cmd = command(project, selected.request, ("--session", selected.id))
    assert "deny" not in run_hook(project, "pre-tool", payload(cmd), host)
    result = cli(
        project, "begin", "--request", selected.request, "--session", selected.id
    )
    event = payload(cmd, response=response(host, result))
    write = state.write_json
    with monkeypatch.context() as patch:
        patch.setattr(
            state, "write_json", lambda path, value: fail_cleanup(path, value, write)
        )
        assert isinstance(startup_context.complete(project, host, event), Err)
    assert work_session_context.resolve_session(project, host, "conversation") == Ok(
        selected.id
    )
    other = work_sessions.start(project, "Later work").value
    assert work_session_context.bind_session(
        project, host, "conversation", other.id
    ) == Ok(other.id)
    work_sessions.remember_current(project, selected.id)
    assert startup_context.complete(project, host, event) == Ok(other.id)
    assert work_session_context.resolve_session(project, host, "conversation") == Ok(
        other.id
    )


def fail_cleanup(path, value, write):
    match (path.name.endswith("-begin.json"), value.get("consumed")):
        case True, True:
            raise OSError("cleanup unavailable")
        case _:
            return write(path, value)


@pytest.mark.parametrize("host", ("codex", "claude"))
@pytest.mark.parametrize("bound", (True, False))
def test_begin_recovers_an_existing_question_in_selected_scope(project, host, bound):
    first = session(project, "First work")
    selected = session(project, "Pending work")
    match bound:
        case True:
            assert work_session_context.bind_session(
                project, host, "conversation", first.id
            ) == Ok(first.id)
        case _:
            pass
    assert isinstance(
        decisions.begin(
            project,
            "review",
            "Continue?",
            ("Continue", "Revise"),
            "chat",
            work_session_id=selected.id,
        ),
        Ok,
    )
    cmd = command(project, selected.request, ("--session", selected.id))
    assert "deny" not in run_hook(project, "pre-tool", payload(cmd), host)
    result = cli(
        project, "begin", "--request", selected.request, "--session", selected.id
    )
    assert result.returncode == 0, result.stderr
    presentation = json.loads(result.stdout)
    assert presentation["state"] == "waiting_for_human"
    assert presentation["options"] == ["Continue", "Revise"]
    assert presentation["id"] == decisions.pending(project, selected.id).id
    assert "not confirmed" not in run_hook(
        project, "startup", payload(cmd, response=response(host, result)), host
    )
    assert work_session_context.resolve_session(project, host, "conversation") == Ok(
        selected.id
    )
    run_hook(
        project, "prompt", {"session_id": "conversation", "prompt": "Continue"}, host
    )
    assert decisions.pending(project, selected.id) is None


def test_begin_cannot_escape_an_unanswered_bound_scope(project):
    first = session(project, "First work")
    selected = session(project, "Other work")
    assert work_session_context.bind_session(
        project, "codex", "conversation", first.id
    ) == Ok(first.id)
    assert isinstance(
        decisions.begin(
            project,
            "review",
            "Continue?",
            ("Continue", "Revise"),
            "chat",
            work_session_id=first.id,
        ),
        Ok,
    )
    cmd = command(project, selected.request, ("--session", selected.id))
    assert "decision-pending" in run_hook(project, "pre-tool", payload(cmd), "codex")


@pytest.mark.parametrize("global_question", (True, False))
def test_pending_recovery_keeps_the_global_gate_and_same_scope_boundary(
    project, global_question
):
    selected = session(project)
    assert work_session_context.bind_session(
        project, "codex", "conversation", selected.id
    ) == Ok(selected.id)
    assert isinstance(
        decisions.begin(
            project,
            "review",
            "Continue?",
            ("Continue", "Revise"),
            "chat",
            work_session_id=None if global_question else selected.id,
        ),
        Ok,
    )
    cmd = command(project, selected.request, ("--session", selected.id))
    assert (
        "decision-pending" in run_hook(project, "pre-tool", payload(cmd), "codex")
    ) == global_question
