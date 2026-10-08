"""Startup recovery and advisory inspection regression cases."""

import json

import pytest

from core.result import Err, Ok
from harness import plan_check, workflow
from tests.harness.test_discovery_render import cli, prepare, session


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    return prepare(tmp_path / "project")


def test_begin_starts_and_reuses(project):
    first = json.loads(cli(project, "begin", "--request", "Show both counts").stdout)
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
    result = json.loads(cli(project, "begin", "--request", selected.request).stdout)
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
    initial = cli(project, "begin", "--request", selected.request)
    entry = json.loads(initial.stdout)["discover_entry"]
    from pathlib import Path

    Path(entry).write_text("Tampered pinned instructions")
    result = cli(project, "begin", "--request", selected.request)
    assert result.returncode != 0


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
