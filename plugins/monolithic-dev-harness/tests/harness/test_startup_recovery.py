"""Startup and explicit resume preserve their validation and selection boundaries."""

from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import discovery, startup, work_sessions, workflow
from tests.harness.test_discovery_render import cli, prepare, session


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    return prepare(tmp_path / "project")


@pytest.mark.parametrize("stage", ("discover", "build"))
@pytest.mark.parametrize("operation", ("pause", "stop"))
@pytest.mark.parametrize("command", ("begin", "resume"))
def test_resume_verifies_before_changing_session_or_pointer(
    project, stage, operation, command
):
    selected = session(project)
    entry = Path(discovery.render(project, selected.id).value["entry"])
    assert isinstance(
        workflow.save(
            project,
            workflow.add_point(
                workflow.load(project, selected.id).value, "Saved work", stage
            ).value,
            selected.id,
        ),
        Ok,
    )
    assert isinstance(work_sessions.transition(project, selected.id, operation), Ok)
    other = work_sessions.start(project, "Other work").value
    entry.write_text("Changed pinned instructions")
    result = resume_command(project, selected, command)
    assert result.returncode != 0
    assert (
        work_sessions.select(project, selected.id).value.status.value
        == {"pause": "paused", "stop": "stopped"}[operation]
    )
    assert work_sessions.current(project) == other.id


def resume_command(project, selected, command):
    match command:
        case "begin":
            return cli(
                project,
                "begin",
                "--request",
                selected.request,
                "--session",
                selected.id,
            )
        case _:
            return cli(project, "work-session", "resume", selected.id)


def test_failed_render_does_not_select_new_session(project, monkeypatch):
    from core.result import err

    previous = work_sessions.start(project, "Existing work").value
    monkeypatch.setattr(
        discovery, "render", lambda *_: err("render_failed", "Test rendering failure")
    )
    assert isinstance(startup.begin(project, "New work", new=True), Err)
    assert work_sessions.current(project) == previous.id


def test_failed_current_selection_returns_a_result_not_an_exception(
    project, monkeypatch
):
    def fail_pointer(*_):
        raise OSError("current selection unavailable")

    monkeypatch.setattr(work_sessions, "remember_current", fail_pointer)
    assert isinstance(work_sessions.start(project, "New work"), Err)


@pytest.mark.parametrize("failure", ("render", "pointer"))
def test_failed_first_startup_is_recoverable_but_not_implicitly_selected(
    project, monkeypatch, failure
):
    from core.result import err

    with monkeypatch.context() as patch:
        match failure:
            case "render":
                patch.setattr(
                    discovery, "render", lambda *_: err("render_failed", "failure")
                )
            case _:
                patch.setattr(work_sessions, "remember_current", fail_selection)
        assert isinstance(startup.begin(project, "First work"), Err)
        assert work_sessions.current(project) is None
    assert len(work_sessions.list_sessions(project).value) == 1
    assert isinstance(startup.begin(project, "First work"), Ok)
    assert (
        work_sessions.current(project)
        == work_sessions.list_sessions(project).value[0].id
    )


def fail_selection(*_):
    raise OSError("selection unavailable")


def test_completed_startup_remains_eligible_after_later_selection_is_paused(project):
    first = startup.begin(project, "First work").value["session_id"]
    second = startup.begin(project, "Second work", new=True).value["session_id"]
    assert isinstance(work_sessions.transition(project, second, "pause"), Ok)
    assert work_sessions.current(project) == first


def test_legacy_session_preserves_implicit_selection(project):
    from harness import state

    selected = work_sessions.start(project, "Legacy work").value
    state.write_json(
        selected.folder / "session.json",
        {
            key: value
            for key, value in state.read_json(selected.folder / "session.json").items()
            if key != "implicit_selection"
        },
    )
    (work_sessions.root(project) / work_sessions.CURRENT).unlink()
    assert work_sessions.current(project) == selected.id
