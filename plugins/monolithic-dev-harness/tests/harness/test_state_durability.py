"""Filesystem guarantees for local JSON state records."""

from __future__ import annotations

import errno
import os
import threading
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, state


def test_write_syncs_contents_before_replacement_and_directory_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state" / "record.json"
    path.parent.mkdir()
    calls: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(descriptor: int) -> None:
        calls.append("fsync")
        real_fsync(descriptor)

    def replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        calls.append("replace")
        real_replace(source, target)

    monkeypatch.setattr(state.os, "fsync", fsync)
    monkeypatch.setattr(state.os, "replace", replace)

    state.write_json(path, {"id": "new"})

    assert state.read_json(path) == {"id": "new"}
    assert calls == ["fsync", "replace"] + ([] if os.name == "nt" else ["fsync"])


def test_failure_before_replacement_preserves_old_record_and_removes_staging_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state" / "record.json"
    state.write_json(path, {"id": "old"})

    def fail_replace(*_args: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(state.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        state.write_json(path, {"id": "new"})

    assert state.read_json(path) == {"id": "old"}
    assert sorted(item.name for item in path.parent.iterdir()) == ["record.json"]


def test_directory_sync_failure_reports_that_replacement_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state" / "record.json"
    path.parent.mkdir()

    def fail_sync(_folder: Path) -> None:
        raise OSError("directory sync failed")

    monkeypatch.setattr(state, "sync_directory", fail_sync)

    with pytest.raises(
        state.StateWriteDurabilityError, match="crash durability is unknown"
    ) as caught:
        state.write_json(path, {"id": "new"})

    assert caught.value.replacement_visible is True
    assert caught.value.path == path
    assert state.read_json(path) == {"id": "new"}
    assert sorted(item.name for item in path.parent.iterdir()) == ["record.json"]


def test_new_directory_chain_syncs_each_parent_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "first" / "second"
    synced: list[Path] = []
    monkeypatch.setattr(state, "sync_directory", synced.append)

    state.ensure_directory(directory)

    assert directory.is_dir()
    assert synced == [tmp_path, tmp_path / "first"]


def test_unsupported_directory_fsync_does_not_claim_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsupported(_descriptor: int) -> None:
        raise OSError(errno.EINVAL, "directory fsync unsupported")

    monkeypatch.setattr(state.os, "fsync", unsupported)

    state.sync_directory(tmp_path)


def test_concurrent_history_updates_preserve_both_entries(tmp_path: Path) -> None:
    path = tmp_path / "decision.json"
    entries = ({"id": "first"}, {"id": "second"})
    outcomes: list[object] = []

    threads = tuple(
        threading.Thread(
            target=lambda entry=entry: outcomes.append(
                decisions.append_history(path, entry)
            )
        )
        for entry in entries
    )
    tuple(thread.start() for thread in threads)
    tuple(thread.join(5) for thread in threads)

    assert all(not thread.is_alive() for thread in threads)
    assert len(outcomes) == 2
    assert all(isinstance(outcome, Ok) for outcome in outcomes)
    assert {
        entry["id"]
        for entry in (state.read_json(path.with_name(decisions.HISTORY)) or {})[
            "answers"
        ]
    } == {"first", "second"}
