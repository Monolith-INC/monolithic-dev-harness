"""A mode's session: entering creates a work session nobody is asked about, and leaving ends it."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.result import Ok
from harness import cli, modes, rules, state, work_sessions
from tests.harness.test_modes import VALID_FIELDS, refusal, write_mode


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    modes_root = tmp_path / "modes"
    write_mode(modes_root, name="fixture", fields=VALID_FIELDS)
    monkeypatch.setattr(modes, "MODES_ROOT", modes_root)
    return project


def entered(result) -> modes.Active:
    match result:
        case Ok(value):
            return value
        case _:
            raise AssertionError(f"expected the mode to be entered, got {result!r}")


def session_status(project: Path, identifier: str) -> work_sessions.Status:
    match work_sessions.select(project, identifier):
        case Ok(session):
            return session.status
        case _:
            raise AssertionError(f"work session {identifier} was not found")


def age_touch(project: Path, hours: int) -> None:
    record = state.read_json(state.mode_record(project))
    assert record is not None
    stale = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    state.write_json(state.mode_record(project), {**record, "touched": stale})


def test_enter_creates_a_session_with_no_question(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))

    sessions = work_sessions.list_sessions(repo)
    assert isinstance(sessions, Ok)
    assert [session.request for session in sessions.value] == ["fixture mode"]
    assert active.session_id == sessions.value[0].id
    assert work_sessions.current(repo) == active.session_id
    assert sorted(path.name for path in state.state_dir(repo).iterdir()) == [
        "mode.json",
        "work_sessions",
    ]
    assert state.read_json(state.mode_record(repo)) == {
        "mode": "fixture",
        "session_id": active.session_id,
        "root": "",
        "entered": active.entered,
        "touched": active.touched,
    }


def test_an_unknown_mode_is_refused_before_any_session_exists(repo: Path) -> None:
    code, _ = refusal(modes.enter(repo, "missing"))

    assert code == "invalid_mode"
    assert work_sessions.list_sessions(repo) == Ok(())
    assert not state.mode_record(repo).exists()


def test_second_enter_is_refused_naming_the_active_mode(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))

    code, message = refusal(modes.enter(repo, "fixture"))

    assert code == "mode_active"
    assert "fixture" in message


def test_leave_completes_the_session_and_clears_the_record(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))

    assert isinstance(modes.leave(repo), Ok)

    assert not state.mode_record(repo).exists()
    assert modes.active(repo) is None
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE


def test_leave_without_an_active_mode_is_refused(repo: Path) -> None:
    code, _ = refusal(modes.leave(repo))

    assert code == "mode_inactive"


def test_a_stale_record_is_cleared_on_read(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))
    age_touch(repo, hours=5)

    assert modes.active(repo) is None
    assert not state.mode_record(repo).exists()
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE
    assert isinstance(modes.enter(repo, "fixture"), Ok)


def test_touch_keeps_a_mode_fresh(repo: Path) -> None:
    entered(modes.enter(repo, "fixture"))
    age_touch(repo, hours=3)

    modes.touch(repo)

    assert modes.active(repo) is not None


def test_the_agent_cannot_write_mode_json_directly(repo: Path) -> None:
    assert rules.is_human_owned(".harness/state/mode.json")
    assert rules.shell_writes_human_owned("echo '{}' > .harness/state/mode.json", repo)


def test_cli_enters_shows_and_leaves_a_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli.main(["modes", "enter", "fixture", "--root", "EPIC-1", "--repo", str(repo)])
        == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert record["mode"] == "fixture"
    assert record["root"] == "EPIC-1"

    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out) == record

    assert cli.main(["modes", "enter", "fixture", "--repo", str(repo)]) == 2
    refusal_report = json.loads(capsys.readouterr().err)
    assert refusal_report["error"] == "mode_active"
    assert "fixture" in refusal_report["message"]

    assert cli.main(["modes", "leave", "--repo", str(repo)]) == 0
    capsys.readouterr()
    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0
    assert capsys.readouterr().out == ""
