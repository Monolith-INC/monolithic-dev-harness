"""Work-session records retain folder identity and expose damaged records to recovery."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.result import Err, Ok
from harness import work_sessions


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
