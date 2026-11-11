"""A mode's session: entering creates a work session nobody is asked about, and leaving ends it.

A mode never just drops. Every read of it is total and repairs what it finds: a broken or missing
pointer is regenerated from the work session that records the mode, a paused session is resumed, and
a completed or missing one is replaced by a new session for the same mode and ROOT.
"""

from __future__ import annotations

import fcntl
import json
import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.result import Ok, err
from harness import cli, modes, rules, state, work_sessions
from tests.harness.test_modes import VALID_FIELDS, refusal, write_mode
from tests.settings_fixture import write_settings

RECOVERED = "Recovered the fixture mode."
UNRECOVERED = (
    "The fixture mode could not be recovered; run `harness modes leave` to end it."
)
# A broken pointer names no mode, so a failure to read the mode at all cannot name one either.
GENERIC_UNRECOVERED = (
    "A mode could not be recovered; run `harness modes leave` to end it."
)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    write_settings(project)
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


def session_of(project: Path, identifier: str) -> work_sessions.Session:
    match work_sessions.select(project, identifier):
        case Ok(session):
            return session
        case _:
            raise AssertionError(f"work session {identifier} was not found")


def session_status(project: Path, identifier: str) -> work_sessions.Status:
    return session_of(project, identifier).status


def pointer(project: Path) -> dict:
    record = state.read_json(state.mode_record(project))
    assert record is not None
    return record


def set_aside(project: Path) -> list[Path]:
    return sorted(state.state_dir(project).glob("mode.json.damaged-*"))


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
    assert pointer(repo) == {
        "mode": "fixture",
        "session_id": active.session_id,
        "root": "",
        "entered": active.entered,
    }


def test_enter_records_the_mode_and_its_root_on_the_session(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture", root="EPIC-1"))

    session = session_of(repo, active.session_id)

    assert (session.mode, session.mode_root) == ("fixture", "EPIC-1")


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


def test_enter_is_refused_in_a_repository_the_harness_does_not_govern(
    repo: Path, tmp_path: Path
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()

    code, message = refusal(modes.enter(bare, "fixture"))

    assert code == "not_governed"
    assert "bootstrap" in message
    assert work_sessions.list_sessions(bare) == Ok(())
    assert not state.mode_record(bare).exists()


def test_cli_enter_is_refused_in_a_repository_the_harness_does_not_govern(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()

    assert cli.main(["modes", "enter", "fixture", "--repo", str(bare)]) == 2

    report = json.loads(capsys.readouterr().err)
    assert report["error"] == "not_governed"
    assert "bootstrap" in report["message"]
    assert not (bare / ".harness").exists()


def test_enter_that_cannot_record_the_mode_leaves_no_live_session_behind(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_json = state.write_json

    def refuse_the_pointer(path: Path, payload: dict) -> None:
        if path == state.mode_record(repo):
            raise OSError("the pointer cannot be written")
        write_json(path, payload)

    monkeypatch.setattr(state, "write_json", refuse_the_pointer)

    code, _ = refusal(modes.enter(repo, "fixture"))

    assert code == "mode_unwritable"
    assert work_sessions.recording_mode(repo) == ()
    assert modes.resolve(repo) == modes.Resolution(None)


def test_leave_completes_the_session_and_clears_the_record(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))

    assert isinstance(modes.leave(repo), Ok)

    assert not state.mode_record(repo).exists()
    assert modes.active(repo) is None
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE


def test_leave_without_an_active_mode_is_refused(repo: Path) -> None:
    code, _ = refusal(modes.leave(repo))

    assert code == "mode_inactive"


def test_a_mode_untouched_for_five_hours_is_still_active(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))
    long_ago = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    state.write_json(
        state.mode_record(repo),
        {**pointer(repo), "entered": long_ago, "touched": long_ago},
    )

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == active.session_id
    assert resolved.notice == ""
    assert session_status(repo, active.session_id) == work_sessions.Status.ACTIVE
    assert not set_aside(repo)


def test_the_agent_cannot_write_mode_json_directly(repo: Path) -> None:
    assert rules.is_human_owned(".harness/state/mode.json")
    assert rules.shell_writes_human_owned("echo '{}' > .harness/state/mode.json", repo)


# a healthy mode


def test_a_healthy_mode_is_read_without_any_repair(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))
    before = state.mode_record(repo).read_bytes()

    resolved = modes.resolve(repo)

    assert resolved.active == active
    assert resolved.notice == ""
    assert state.mode_record(repo).read_bytes() == before
    assert not set_aside(repo)


def test_no_mode_and_no_record_is_quiet_and_writes_nothing(repo: Path) -> None:
    assert modes.resolve(repo) == modes.Resolution(None)

    assert not state.state_dir(repo).exists()


# a broken pointer


def invalid_utf8(path: Path, record: dict) -> None:
    path.write_bytes(b"\xff\xfe")


def invalid_json(path: Path, record: dict) -> None:
    path.write_text("{damaged", encoding="utf-8")


def not_an_object(path: Path, record: dict) -> None:
    path.write_text("[]", encoding="utf-8")


def without_root(path: Path, record: dict) -> None:
    record.pop("root")
    path.write_text(json.dumps(record), encoding="utf-8")


def with_a_naive_time(path: Path, record: dict) -> None:
    path.write_text(
        json.dumps({**record, "entered": "2026-11-11T10:00:00"}), encoding="utf-8"
    )


def with_an_unknown_mode(path: Path, record: dict) -> None:
    path.write_text(json.dumps({**record, "mode": "gone"}), encoding="utf-8")


def a_directory(path: Path, record: dict) -> None:
    path.unlink()
    path.mkdir()


BREAKAGES = [
    invalid_utf8,
    invalid_json,
    not_an_object,
    without_root,
    with_a_naive_time,
    with_an_unknown_mode,
    a_directory,
]


def break_pointer(project: Path, breakage: Callable[[Path, dict], None]) -> bytes:
    """Break the pointer with `breakage`; the bytes it was left with, for comparison."""
    path = state.mode_record(project)
    breakage(path, pointer(project))
    return path.read_bytes() if path.is_file() else b""


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda fn: fn.__name__)
def test_a_broken_pointer_with_a_live_session_is_set_aside_and_regenerated(
    repo: Path, breakage: Callable[[Path, dict], None]
) -> None:
    active = entered(modes.enter(repo, "fixture", root="EPIC-1"))
    broken = break_pointer(repo, breakage)

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == active.session_id
    assert (resolved.active.mode, resolved.active.root) == ("fixture", "EPIC-1")
    assert resolved.notice == RECOVERED
    assert active.session_id not in resolved.notice
    kept = set_aside(repo)
    assert len(kept) == 1
    assert (kept[0].read_bytes() if kept[0].is_file() else b"") == broken
    assert pointer(repo)["session_id"] == active.session_id
    assert pointer(repo)["root"] == "EPIC-1"
    assert len(work_sessions.recording_mode(repo)) == 1
    assert modes.resolve(repo).notice == ""


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda fn: fn.__name__)
def test_a_broken_pointer_with_no_mode_session_is_set_aside_and_there_is_no_mode(
    repo: Path, breakage: Callable[[Path, dict], None]
) -> None:
    state.write_json(
        state.mode_record(repo),
        {
            "mode": "fixture",
            "session_id": "WS-000000000000",
            "root": "",
            "entered": datetime.now(UTC).isoformat(),
        },
    )
    break_pointer(repo, breakage)

    assert modes.resolve(repo) == modes.Resolution(None)

    assert len(set_aside(repo)) == 1
    assert not state.mode_record(repo).exists()


def test_a_deleted_pointer_with_a_live_mode_session_is_regenerated(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture", root="EPIC-1"))
    state.mode_record(repo).unlink()

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == active.session_id
    assert resolved.notice == RECOVERED
    assert pointer(repo)["session_id"] == active.session_id
    assert not set_aside(repo)
    assert modes.resolve(repo).notice == ""


def test_a_session_for_a_mode_nobody_knows_is_not_regenerated(repo: Path) -> None:
    other = work_sessions.create(repo, "gone mode", mode="gone")
    assert isinstance(other, Ok)

    resolved = modes.resolve(repo)

    assert resolved == modes.Resolution(None, UNRECOVERED.replace("fixture", "gone"))
    assert not state.mode_record(repo).exists()


# a mode session that is not live


def test_a_paused_mode_session_is_resumed(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(work_sessions.transition(repo, active.session_id, "pause"), Ok)

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == active.session_id
    assert resolved.notice == RECOVERED
    assert session_status(repo, active.session_id) == work_sessions.Status.ACTIVE
    assert len(work_sessions.recording_mode(repo)) == 1
    assert modes.resolve(repo).notice == ""


def test_a_session_another_call_just_resumed_is_not_a_failed_repair(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    assert isinstance(work_sessions.transition(repo, active.session_id, "pause"), Ok)
    transition = work_sessions.transition

    def lose_the_race(project: Path, identifier: str, operation: str, **options):
        transition(project, identifier, operation, **options)  # the other call won
        return transition(project, identifier, operation, **options)

    monkeypatch.setattr(work_sessions, "transition", lose_the_race)

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == active.session_id
    assert resolved.notice == RECOVERED


def end_by_completing(project: Path, active: modes.Active) -> None:
    work_sessions.transition(project, active.session_id, "complete")


def end_by_stopping(project: Path, active: modes.Active) -> None:
    work_sessions.transition(project, active.session_id, "stop")


def end_by_deleting(project: Path, active: modes.Active) -> None:
    shutil.rmtree(session_of(project, active.session_id).folder)


@pytest.mark.parametrize(
    "ending",
    [end_by_completing, end_by_stopping, end_by_deleting],
    ids=lambda fn: fn.__name__,
)
def test_an_ended_or_missing_mode_session_is_replaced_for_the_same_mode_and_root(
    repo: Path, ending: Callable[[Path, modes.Active], None]
) -> None:
    active = entered(modes.enter(repo, "fixture", root="EPIC-1"))
    ending(repo, active)

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    new = resolved.active
    assert new.session_id != active.session_id
    assert (new.mode, new.root, new.entered) == ("fixture", "EPIC-1", active.entered)
    assert resolved.notice == RECOVERED
    assert active.session_id not in resolved.notice
    created = session_of(repo, new.session_id)
    assert created.status == work_sessions.Status.ACTIVE
    assert (created.mode, created.mode_root) == ("fixture", "EPIC-1")
    assert pointer(repo)["session_id"] == new.session_id
    assert work_sessions.current(repo) == new.session_id
    assert modes.resolve(repo).notice == ""


# a repair that cannot be done


def test_a_repair_that_cannot_be_written_means_no_mode_for_that_call(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).unlink()
    with monkeypatch.context() as unwritable:

        def refuse(path: Path, payload: dict) -> None:
            raise OSError("nothing can be written")

        unwritable.setattr(state, "write_json", refuse)

        assert modes.resolve(repo) == modes.Resolution(None, UNRECOVERED)

    retried = modes.resolve(repo)
    assert retried.active is not None
    assert retried.active.session_id == active.session_id
    assert retried.notice == RECOVERED


def test_a_pointer_that_cannot_be_moved_aside_is_no_mode_and_says_so(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered(modes.enter(repo, "fixture"))
    break_pointer(repo, invalid_json)

    def refuse(_: Path) -> None:
        raise OSError("cannot move the file")

    monkeypatch.setattr(modes, "_set_aside", refuse)

    assert modes.active(repo) is None
    assert modes.resolve(repo) == modes.Resolution(None, GENERIC_UNRECOVERED)


def test_an_unexpected_failure_reading_the_mode_is_said_never_swallowed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(_: Path) -> modes.Resolution:
        raise RuntimeError("something nobody planned for")

    monkeypatch.setattr(modes, "_resolved", explode)

    assert modes.resolve(repo) == modes.Resolution(None, GENERIC_UNRECOVERED)
    assert "RuntimeError" not in modes.resolve(repo).notice


def refuse_the_pointer(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From now on the pointer cannot be written, so a mode that needs it repaired cannot be."""
    write_json = state.write_json

    def refuse(path: Path, payload: dict) -> None:
        if path == state.mode_record(project):
            raise OSError("the pointer cannot be written")
        write_json(path, payload)

    monkeypatch.setattr(state, "write_json", refuse)


def test_enter_is_refused_while_a_mode_cannot_be_recovered(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).unlink()
    refuse_the_pointer(repo, monkeypatch)

    code, message = refusal(modes.enter(repo, "fixture"))

    assert code == "mode_active"
    assert "harness modes leave" in message
    assert len(work_sessions.recording_mode(repo)) == 1


# leaving, whatever state the mode is in


def test_leave_ends_every_mode_session_even_when_several_are_live(
    repo: Path,
) -> None:
    first = entered(modes.enter(repo, "fixture"))
    second = work_sessions.create(repo, "other", mode="fixture")
    assert isinstance(second, Ok)
    state.mode_record(repo).unlink()

    assert isinstance(modes.leave(repo), Ok)

    assert session_status(repo, first.session_id) == work_sessions.Status.COMPLETE
    assert session_status(repo, second.value.id) == work_sessions.Status.COMPLETE
    assert modes.resolve(repo) == modes.Resolution(None)


def test_leave_ends_a_mode_whose_pointer_is_broken(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))
    break_pointer(repo, invalid_utf8)

    assert isinstance(modes.leave(repo), Ok)

    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE
    assert not state.mode_record(repo).exists()
    assert modes.resolve(repo) == modes.Resolution(None)


def test_leave_does_not_bring_back_a_mode_whose_session_already_ended(
    repo: Path,
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    end_by_completing(repo, active)

    assert isinstance(modes.leave(repo), Ok)

    assert not state.mode_record(repo).exists()
    assert work_sessions.recording_mode(repo) == ()
    assert modes.resolve(repo) == modes.Resolution(None)


# leaving is safe to interrupt: the mode mark goes first, so nothing is left to recover


def test_leave_clears_the_mode_mark_before_it_completes_the_session(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    seen: list[tuple[str, str, bool]] = []
    transition = work_sessions.transition

    def watched(project: Path, identifier: str, operation: str, **options):
        seen.append(
            (
                operation,
                session_of(project, identifier).mode,
                state.mode_record(project).exists(),
            )
        )
        return transition(project, identifier, operation, **options)

    monkeypatch.setattr(work_sessions, "transition", watched)

    assert isinstance(modes.leave(repo), Ok)

    assert seen == [("complete", "", True)]
    assert not state.mode_record(repo).exists()
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE


def interrupted_after_the_mark(repo: Path, active: modes.Active) -> None:
    assert isinstance(work_sessions.unmark(repo, active.session_id), Ok)


def interrupted_after_the_completion(repo: Path, active: modes.Active) -> None:
    interrupted_after_the_mark(repo, active)
    assert isinstance(work_sessions.transition(repo, active.session_id, "complete"), Ok)


@pytest.mark.parametrize(
    "interrupted",
    [interrupted_after_the_mark, interrupted_after_the_completion],
    ids=lambda fn: fn.__name__,
)
def test_a_leave_that_stopped_part_way_leaves_nothing_to_recover(
    repo: Path, interrupted: Callable[[Path, modes.Active], None]
) -> None:
    active = entered(modes.enter(repo, "fixture", root="EPIC-1"))
    interrupted(repo, active)

    assert modes.resolve(repo) == modes.Resolution(None)

    assert not state.mode_record(repo).exists()
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE
    assert work_sessions.recording_mode(repo) == ()
    assert len(work_sessions.list_sessions(repo).value) == 1  # type: ignore[union-attr]
    assert modes.resolve(repo) == modes.Resolution(None)


class Stopped(BaseException):
    """A call that dies between two steps: nothing catches it."""


def test_a_leave_killed_before_it_wrote_anything_changes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))

    def die(*arguments, **options):
        raise Stopped

    with monkeypatch.context() as killed:
        killed.setattr(work_sessions, "unmark", die)
        with pytest.raises(Stopped):
            modes.leave(repo)

    assert modes.resolve(repo) == modes.Resolution(active)
    assert len(work_sessions.list_sessions(repo).value) == 1  # type: ignore[union-attr]


def test_a_leave_killed_after_the_mark_is_not_brought_back_by_the_next_read(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))

    def die(*arguments, **options):
        raise Stopped

    with monkeypatch.context() as killed:
        killed.setattr(work_sessions, "transition", die)
        with pytest.raises(Stopped):
            modes.leave(repo)

    assert modes.resolve(repo) == modes.Resolution(None)
    assert len(work_sessions.list_sessions(repo).value) == 1  # type: ignore[union-attr]
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE


def test_leave_reports_a_session_it_could_not_complete(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    transition = work_sessions.transition

    def unwritable(project: Path, identifier: str, operation: str, **options):
        return err("session_unwritable", f"could not update work session {identifier}")

    monkeypatch.setattr(work_sessions, "transition", unwritable)

    code, message = refusal(modes.leave(repo))

    assert code == "mode_unwritable"
    assert active.session_id not in message
    assert state.mode_record(repo).exists()
    monkeypatch.setattr(work_sessions, "transition", transition)
    assert modes.resolve(repo) == modes.Resolution(None)
    assert session_status(repo, active.session_id) == work_sessions.Status.COMPLETE


def test_leave_reports_a_session_it_could_not_unmark(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))

    def unwritable(project: Path, identifier: str):
        return err("session_unwritable", f"could not update work session {identifier}")

    monkeypatch.setattr(work_sessions, "unmark", unwritable)

    code, message = refusal(modes.leave(repo))

    assert code == "mode_unwritable"
    assert active.session_id not in message
    assert session_status(repo, active.session_id) == work_sessions.Status.ACTIVE
    assert state.mode_record(repo).exists()


def test_cli_leave_reports_a_failure_to_end_the_mode(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    capsys.readouterr()
    monkeypatch.setattr(
        work_sessions,
        "transition",
        lambda *arguments, **options: err("session_unwritable", "write failed"),
    )

    assert cli.main(["modes", "leave", "--repo", str(repo)]) == 2

    assert json.loads(capsys.readouterr().err)["error"] == "mode_unwritable"


def test_leave_waits_for_a_repair_in_progress_and_gives_up_when_it_never_ends(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered(modes.enter(repo, "fixture"))
    monkeypatch.setattr(modes, "REPAIR_WAIT_SECONDS", 0.05)
    lock = state.mode_lock(repo)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)

        code, _ = refusal(modes.leave(repo))

    assert code == "mode_unwritable"
    assert state.mode_record(repo).exists()
    assert isinstance(modes.leave(repo), Ok)


# reading never raises


def test_reading_the_mode_never_raises_on_a_pointer_it_cannot_decode(
    repo: Path,
) -> None:
    state.mode_record(repo).parent.mkdir(parents=True)
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    assert modes.active(repo) is None


# the command line


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


def test_cli_status_recovers_a_broken_pointer_and_shows_the_mode(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture", root="EPIC-1"))
    capsys.readouterr()
    break_pointer(repo, invalid_utf8)

    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0

    out, error = capsys.readouterr()
    shown = json.loads(out)
    assert (shown["mode"], shown["root"]) == ("fixture", "EPIC-1")
    assert error.strip() == RECOVERED


def test_cli_status_says_when_the_mode_could_not_be_recovered(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).unlink()
    refuse_the_pointer(repo, monkeypatch)
    capsys.readouterr()

    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0

    out, error = capsys.readouterr()
    assert out == ""
    assert error.strip() == UNRECOVERED


def test_cli_status_of_a_healthy_mode_prints_no_line_to_stderr(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entered(modes.enter(repo, "fixture"))
    capsys.readouterr()

    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0

    assert capsys.readouterr().err == ""


def test_cli_status_is_silent_for_a_broken_pointer_no_session_backs(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state.mode_record(repo).parent.mkdir(parents=True)
    state.mode_record(repo).write_bytes(b"\xff\xfe")

    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0

    assert capsys.readouterr().out == ""


def test_cli_never_prints_the_mode_session_id(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["modes", "enter", "fixture", "--repo", str(repo)]) == 0
    entered_output = capsys.readouterr().out
    assert cli.main(["modes", "status", "--repo", str(repo)]) == 0
    status_output = capsys.readouterr().out

    active = modes.active(repo)
    assert active is not None
    for output in (entered_output, status_output):
        assert active.session_id not in output
        assert "session" not in output
        assert json.loads(output)["mode"] == "fixture"


def test_cli_from_a_project_subfolder_uses_the_project_root(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    subfolder = repo / "plugins" / "x"
    subfolder.mkdir(parents=True)
    monkeypatch.chdir(subfolder)

    assert cli.main(["modes", "enter", "fixture"]) == 0
    assert modes.active(repo) is not None
    assert not (subfolder / ".harness").exists()
    capsys.readouterr()

    assert cli.main(["modes", "status"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "fixture"

    assert cli.main(["modes", "leave"]) == 0
    assert modes.active(repo) is None
    assert not (subfolder / ".harness").exists()
