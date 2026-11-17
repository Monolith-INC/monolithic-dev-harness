"""Work-session records retain folder identity and expose damaged records to recovery."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import state, work_sessions


def test_copied_project_keeps_sessions_and_transitions_local_to_the_copy(
    tmp_path: Path,
) -> None:
    source, copy = tmp_path / "source", tmp_path / "copy"
    source.mkdir()
    first = work_sessions.start(source, "Investigate DAY-001").value
    second = work_sessions.start(source, "Investigate DAY-002").value
    shutil.copytree(source, copy)

    listed = work_sessions.list_sessions(copy).value
    selected = work_sessions.select(copy, first.id).value
    paused = work_sessions.transition(copy, first.id, "pause").value

    assert {session.id for session in listed} == {first.id, second.id}
    assert all(session.folder.parent == work_sessions.root(copy) for session in listed)
    assert selected.folder == work_sessions.root(copy) / first.id
    assert paused.status is work_sessions.Status.PAUSED
    assert (
        work_sessions.select(source, first.id).value.status
        is work_sessions.Status.ACTIVE
    )
    copied_record = json.loads((selected.folder / "session.json").read_text())
    assert copied_record["id"] == first.id
    assert copied_record["version"] == work_sessions.VERSION
    assert "project_root" not in copied_record


def test_legacy_valid_record_remains_readable(tmp_path: Path) -> None:
    session = work_sessions.start(tmp_path, "Investigate DAY-001").value
    record_path = session.folder / "session.json"
    record = json.loads(record_path.read_text())
    record.update(
        {
            "version": work_sessions.VERSION,
            "id": session.id,
            "project_root": str(tmp_path.resolve()),
        }
    )
    record_path.write_text(json.dumps(record))

    assert work_sessions.select(tmp_path, session.id) == Ok(session)


def test_mismatched_record_id_is_reported_as_damaged(tmp_path: Path) -> None:
    session = work_sessions.start(tmp_path, "Investigate DAY-001").value
    record_path = session.folder / "session.json"
    record = json.loads(record_path.read_text())
    record["id"] = "WS-other"
    record_path.write_text(json.dumps(record))

    assert isinstance(work_sessions.select(tmp_path, session.id), Err)
    readable, damaged = work_sessions.scan(tmp_path)
    assert session.id not in {item.id for item in readable}
    assert record_path in damaged
    assert isinstance(work_sessions.list_sessions(tmp_path), Err)


def test_session_directory_sync_failure_reports_created_session_as_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work_sessions.root(tmp_path).mkdir(parents=True)

    real_sync = state.sync_directory
    calls = 0

    def fail_after_record_sync(directory: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            real_sync(directory)
        else:
            raise OSError("directory sync failed")

    monkeypatch.setattr(state, "sync_directory", fail_after_record_sync)

    created = work_sessions.create(tmp_path, "Investigate DAY-003")

    assert isinstance(created, Err)
    sessions = tuple(work_sessions.root(tmp_path).glob("*/session.json"))
    assert len(sessions) == 1
    assert state.read_json(sessions[0]) is not None
    assert "visible" in created.failure.message


def test_staging_directory_sync_failure_reports_no_published_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions_root = work_sessions.root(tmp_path)
    sessions_root.mkdir(parents=True)

    real_sync = state.sync_directory

    def fail_staging_sync(directory: Path) -> None:
        if directory.parent == sessions_root and directory.name.endswith(".tmp"):
            raise OSError("directory sync failed")
        real_sync(directory)

    monkeypatch.setattr(state, "sync_directory", fail_staging_sync)

    created = work_sessions.create(tmp_path, "Investigate DAY-006")

    assert isinstance(created, Err)
    assert "temporary folder was removed before publication" in created.failure.message
    assert "visible" not in created.failure.message
    assert tuple(sessions_root.iterdir()) == ()


def test_reserved_session_directory_sync_failure_is_not_recovered_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work_sessions.root(tmp_path).mkdir(parents=True)
    identifier = "WS-0123456789abcdef01234567"
    real_sync = state.sync_directory
    calls = 0

    def fail_after_record_sync(directory: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            real_sync(directory)
        else:
            raise OSError("directory sync failed")

    monkeypatch.setattr(state, "sync_directory", fail_after_record_sync)

    created = work_sessions.create_reserved(tmp_path, "Investigate DAY-005", identifier)

    assert isinstance(created, Err)
    assert "crash durability is unknown" in created.failure.message
    assert (work_sessions.root(tmp_path) / identifier / "session.json").is_file()


def test_resume_keeps_current_pointer_when_session_replace_is_visible_but_unsynced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = work_sessions.start(tmp_path, "Investigate DAY-004").value
    paused = work_sessions.transition(tmp_path, session.id, "pause")
    assert isinstance(paused, Ok)
    real_sync = state.sync_directory
    failed = False

    def fail_once(directory: Path) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("directory sync failed")
        real_sync(directory)

    monkeypatch.setattr(state, "sync_directory", fail_once)

    resumed = work_sessions.transition(tmp_path, session.id, "resume")

    assert isinstance(resumed, Err)
    assert state.read_json(session.folder / "session.json")["status"] == "active"
    assert work_sessions.current(tmp_path) == session.id


def test_record_requires_valid_id_and_version(tmp_path: Path) -> None:
    session = work_sessions.start(tmp_path, "Investigate DAY-001").value
    record_path = session.folder / "session.json"
    original = json.loads(record_path.read_text())

    for changes in (
        {"id": None},
        {"version": None},
        {"version": work_sessions.VERSION + 1},
        {"version": True},
    ):
        record_path.write_text(json.dumps({**original, **changes}))
        assert isinstance(work_sessions.select(tmp_path, session.id), Err)

    record_path.write_text(
        json.dumps({key: value for key, value in original.items() if key != "id"})
    )
    assert isinstance(work_sessions.select(tmp_path, session.id), Err)

    record_path.write_text(
        json.dumps({key: value for key, value in original.items() if key != "version"})
    )
    assert isinstance(work_sessions.select(tmp_path, session.id), Err)


def test_arbitrary_corrupt_bytes_remain_visible_to_recovery(tmp_path: Path) -> None:
    folder = work_sessions.root(tmp_path) / "WS-damaged"
    folder.mkdir(parents=True)
    record_path = folder / "session.json"
    record_path.write_bytes(bytes(range(256)) * 4)

    readable, damaged = work_sessions.scan(tmp_path)

    assert readable == ()
    assert damaged == (record_path,)
    assert isinstance(work_sessions.list_sessions(tmp_path), Err)
