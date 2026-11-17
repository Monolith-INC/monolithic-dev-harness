"""Startup recovery and advisory inspection regression cases."""

import json

import pytest

from core.result import Err, Ok
from harness import plan_check, session_entry, startup, workflow
from host_adapters import work_session_context
from tests.harness.test_discovery_render import cli, prepare, session


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    monkeypatch.setenv("CODEX_THREAD_ID", "less-friction-thread")
    return prepare(tmp_path / "project")


def choose_saved_work(
    project, request, option_key, conversation="less-friction-thread"
):
    host = "codex"
    assert isinstance(
        startup.begin(project, request, host=host, conversation=conversation), Ok
    )
    prepared = session_entry.current_offer(project, host, conversation).value
    index = next(
        index for index, item in enumerate(prepared.options) if item.key == option_key
    )
    question = session_entry.question(prepared, "en")
    payload = {
        "session_id": conversation,
        "tool_use_id": "explicit-saved-work-choice",
        "tool_name": "request_user_input",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(project, host, payload).value
    assert (
        session_entry.answer(
            project,
            host,
            {
                **payload,
                "tool_response": {
                    "answers": {
                        question["question"]: question["options"][index]["label"]
                    }
                },
            },
        ).value
        == option_key
    )
    return session_entry.apply_selection(project, host, conversation)


def test_begin_starts_and_reuses(project):
    first = json.loads(cli(project, "begin", "--request", "Show both counts").stdout)
    assert (
        work_session_context.bind_session(
            project, "codex", "less-friction-thread", first["session_id"]
        ).value
        == first["session_id"]
    )
    second = json.loads(cli(project, "begin", "--request", "Show both counts").stdout)
    assert first["state"] == "active"
    assert first["discover_entry"]
    assert first["session_id"] == second["session_id"]


def test_begin_does_not_resume_paused_workflow(project):
    selected = session(project)
    current = workflow.load(project, selected.id).value
    assert isinstance(
        workflow.save(project, workflow.pause(current).value, selected.id), Ok
    )
    chosen = choose_saved_work(project, selected.request, f"continue:{selected.id}")
    assert isinstance(chosen, Ok) and chosen.value == selected.id
    result = startup.begin(
        project, selected.request, host="codex", conversation="less-friction-thread"
    ).value
    assert result["state"] == "paused"
    assert result["discover_entry"] == ""


def test_artifact_question_saves_checkpoint(project):
    selected = session(project)
    (project / "plan.md").write_text("Reviewed plan")
    result = cli(
        project,
        "decision",
        "present",
        "--question",
        "Use this plan?",
        "--option",
        "Continue",
        "--option",
        "Revise",
        "--artifact",
        "plan.md",
        "--host",
        "text",
    )
    assert result.returncode == 0, result.stderr
    current = workflow.load(project, selected.id).value
    assert current.current.pending == "Use this plan?"
    assert current.current.artifacts[0][0] == "plan.md"


def test_plan_inspection_handles_missing_file(tmp_path):
    assert isinstance(plan_check.check(tmp_path / "absent.md"), Err)
    assert plan_check.inspect("Linux offline invitations")["scope_signals"] == [
        "Linux",
        "offline",
        "invitations",
    ]


def test_question_without_session_still_works(project):
    (project / "plan.md").write_text("Plan without session")
    result = cli(
        project,
        "decision",
        "present",
        "--question",
        "Use this plan?",
        "--option",
        "Continue",
        "--option",
        "Revise",
        "--artifact",
        "plan.md",
        "--host",
        "text",
    )
    assert result.returncode == 0, result.stderr


def test_begin_does_not_hide_render_failure(project):
    selected = session(project)
    chosen = choose_saved_work(project, selected.request, f"continue:{selected.id}")
    assert isinstance(chosen, Ok)
    entry = startup.begin(
        project, selected.request, host="codex", conversation="less-friction-thread"
    ).value["discover_entry"]
    from pathlib import Path

    Path(entry).write_text("Tampered pinned instructions")
    result = startup.begin(
        project, selected.request, host="codex", conversation="less-friction-thread"
    )
    assert isinstance(result, Err)


def test_question_with_paused_workflow_still_works(project):
    selected = session(project)
    assert isinstance(
        workflow.save(
            project,
            workflow.pause(workflow.load(project, selected.id).value).value,
            selected.id,
        ),
        Ok,
    )
    (project / "plan.md").write_text("Paused review")
    result = cli(
        project,
        "decision",
        "present",
        "--session-id",
        selected.id,
        "--question",
        "Use this plan?",
        "--option",
        "Continue",
        "--option",
        "Revise",
        "--artifact",
        "plan.md",
        "--host",
        "text",
    )
    assert result.returncode == 0, result.stderr
    assert workflow.load(project, selected.id).value.status == "paused"
