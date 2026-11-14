"""Hooks of parallel tool calls each read the mode, so each may find it needing the same repair.

One repair is enough. The others read the repaired mode, say nothing, and leave a single live mode
session behind. Each case here runs real processes, started together, because a thread in this
interpreter does not race the way a host's parallel hooks do.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from core.result import Ok
from harness import modes, state, work_sessions
from tests.harness.test_mode_session import (
    RECOVERED,
    entered,
    pointer,
    set_aside,
)
from tests.harness.test_modes import VALID_FIELDS, write_mode
from tests.settings_fixture import write_settings

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PROCESSES = 4
TRIALS = 4

# Each process waits at the start line, so all of them read the broken mode at the same moment.
RACER = """
import json, sys, time
from pathlib import Path
from harness import modes

repo, modes_root, ready, go = (Path(argument) for argument in sys.argv[1:5])
modes.MODES_ROOT = modes_root
ready.touch()
while not go.exists():
    time.sleep(0.0002)
resolved = modes.resolve(repo)
print(json.dumps({
    "notice": resolved.notice,
    "session": resolved.active.session_id if resolved.active else None,
}))
"""


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    write_settings(project)
    write_mode(tmp_path / "modes", name="fixture", fields=VALID_FIELDS)
    monkeypatch.setattr(modes, "MODES_ROOT", tmp_path / "modes")
    return project


def race(repo: Path, modes_root: Path, trial: Path) -> list[dict]:
    """Read the mode from `PROCESSES` processes started together; what each one saw."""
    trial.mkdir()
    go = trial / "go"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([".", "scripts"])}
    racers = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                RACER,
                str(repo),
                str(modes_root),
                str(trial / f"ready-{number}"),
                str(go),
            ],
            cwd=PLUGIN_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for number in range(PROCESSES)
    ]
    deadline = time.monotonic() + 30
    while len(list(trial.glob("ready-*"))) < PROCESSES:
        assert time.monotonic() < deadline, "the processes never got ready"
        time.sleep(0.01)
    go.touch()
    seen = []
    for racer in racers:
        out, error = racer.communicate(timeout=60)
        assert racer.returncode == 0, error
        seen.append(json.loads(out))
    return seen


def test_parallel_reads_of_a_mode_whose_session_ended_repair_it_once(
    repo: Path, tmp_path: Path
) -> None:
    for trial in range(TRIALS):
        stale = work_sessions.recording_mode(repo)
        active = (
            entered(modes.enter(repo, "fixture", root="EPIC-1"))
            if not stale
            else modes.active(repo)
        )
        assert active is not None
        assert isinstance(
            work_sessions.transition(repo, active.session_id, "complete"), Ok
        )

        seen = race(repo, tmp_path / "modes", tmp_path / f"trial-{trial}")

        failures = [one["notice"] for one in seen if "could not" in one["notice"]]
        assert failures == [], f"trial {trial}: spurious notices {failures}"
        assert all(one["session"] for one in seen), f"trial {trial}: a call had no mode"
        assert len({one["session"] for one in seen}) == 1
        assert [one["notice"] for one in seen].count(RECOVERED) == 1
        live = work_sessions.recording_mode(repo)
        assert len(live) == 1, f"trial {trial}: {len(live)} live mode sessions"
        assert live[0].id == seen[0]["session"]
        assert pointer(repo)["session_id"] == live[0].id
        assert work_sessions.current(repo) == live[0].id
        assert not set_aside(repo)


def test_parallel_writers_of_one_state_file_never_collide(tmp_path: Path) -> None:
    target = tmp_path / "state" / "record.json"
    failures: list[BaseException] = []
    start = threading.Barrier(PROCESSES)

    def write(writer: int) -> None:
        start.wait()
        try:
            for step in range(300):
                state.write_json(target, {"writer": writer, "step": step})
        except BaseException as exc:
            failures.append(exc)

    writers = [threading.Thread(target=write, args=(n,)) for n in range(PROCESSES)]
    for thread in writers:
        thread.start()
    for thread in writers:
        thread.join()

    assert failures == []
    assert state.read_json(target) is not None
    assert [path.name for path in target.parent.iterdir()] == ["record.json"]


def test_a_failed_write_leaves_no_staging_file_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state" / "record.json"

    def refuse(self: Path, destination: Path) -> None:
        raise OSError("the file cannot be replaced")

    monkeypatch.setattr(Path, "replace", refuse)

    with pytest.raises(OSError):
        state.write_json(target, {"writer": 1})

    assert list(target.parent.iterdir()) == []


# more than one live mode session: the oldest is the mode, the others end


def second_live_session(repo: Path) -> work_sessions.Session:
    created = work_sessions.create(repo, "fixture mode", mode="fixture")
    assert isinstance(created, Ok)
    return created.value


def test_with_several_live_mode_sessions_the_oldest_stays_and_the_others_end(
    repo: Path,
) -> None:
    first = entered(modes.enter(repo, "fixture", root="EPIC-1"))
    second = second_live_session(repo)
    third = second_live_session(repo)
    state.mode_record(repo).unlink()

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == first.session_id
    assert resolved.notice == RECOVERED
    status = {
        item.id: item.status
        for item in work_sessions.list_sessions(repo).value  # type: ignore[union-attr]
    }
    assert status[first.session_id] == work_sessions.Status.ACTIVE
    assert status[second.id] == work_sessions.Status.COMPLETE
    assert status[third.id] == work_sessions.Status.COMPLETE
    assert pointer(repo)["session_id"] == first.session_id
    assert modes.resolve(repo) == modes.Resolution(resolved.active)


def test_the_oldest_live_mode_session_is_kept_even_when_it_is_paused(
    repo: Path,
) -> None:
    first = entered(modes.enter(repo, "fixture"))
    second = second_live_session(repo)
    assert isinstance(work_sessions.transition(repo, first.session_id, "pause"), Ok)
    state.mode_record(repo).unlink()

    resolved = modes.resolve(repo)

    assert resolved.active is not None
    assert resolved.active.session_id == first.session_id
    status = {
        item.id: item.status
        for item in work_sessions.list_sessions(repo).value  # type: ignore[union-attr]
    }
    assert status[first.session_id] == work_sessions.Status.ACTIVE
    assert status[second.id] == work_sessions.Status.COMPLETE


# the lock


def hold_the_repair_lock(repo: Path):
    """Another call mid-repair: the lock is held until the returned handle is closed."""
    lock = state.mode_lock(repo)
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = lock.open("a")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def test_a_repair_that_cannot_get_the_lock_in_time_is_said_not_waited_for_forever(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = entered(modes.enter(repo, "fixture"))
    state.mode_record(repo).write_bytes(b"\xff\xfe")
    monkeypatch.setattr(modes, "REPAIR_WAIT_SECONDS", 0.05)
    holder = hold_the_repair_lock(repo)
    try:
        started = time.monotonic()
        resolved = modes.resolve(repo)
        waited = time.monotonic() - started
    finally:
        holder.close()

    assert resolved.active is None
    assert "could not be recovered" in resolved.notice
    assert waited < 2
    retried = modes.resolve(repo)
    assert retried.active is not None
    assert retried.active.session_id == active.session_id


def test_a_healthy_mode_is_read_without_the_lock(repo: Path) -> None:
    active = entered(modes.enter(repo, "fixture"))
    holder = hold_the_repair_lock(repo)
    try:
        resolved = modes.resolve(repo)
    finally:
        holder.close()

    assert resolved == modes.Resolution(active)
