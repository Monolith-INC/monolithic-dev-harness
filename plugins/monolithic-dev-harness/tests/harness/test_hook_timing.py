"""Each hook event leaves one line in a local log saying what it spent its time on."""

from __future__ import annotations

from pathlib import Path

from harness import decisions, hook_timing, state
from tests.harness.test_decisions import native


def _log(repo: Path) -> list[str]:
    return (state.state_dir(repo) / hook_timing.LOG_NAME).read_text().splitlines()


def test_a_line_names_the_event_the_decision_and_the_elapsed_time(
    tmp_path: Path, monkeypatch
) -> None:
    state.state_dir(tmp_path).mkdir(parents=True)
    now = [100.0]
    monkeypatch.setattr(hook_timing.time, "monotonic", lambda: now[0])
    hook_timing.begin(100.0)
    now[0] = 100.5
    hook_timing.step("context")
    hook_timing.decision("d1")
    now[0] = 101.25
    hook_timing.step("resolve")

    hook_timing.write(tmp_path, "answer", "claude")

    (line,) = _log(tmp_path)
    assert "event=answer" in line and "host=claude" in line
    assert "decision=d1" in line and "elapsed=1.250" in line
    assert "slow=" not in line


def test_a_step_over_two_seconds_is_named_as_the_slowest(
    tmp_path: Path, monkeypatch
) -> None:
    state.state_dir(tmp_path).mkdir(parents=True)
    now = [0.0]
    monkeypatch.setattr(hook_timing.time, "monotonic", lambda: now[0])
    hook_timing.begin(0.0)
    for name, at in (("context", 2.5), ("resolve", 6.0), ("marker", 6.1)):
        now[0] = at
        hook_timing.step(name)

    hook_timing.write(tmp_path, "answer", "claude")

    (line,) = _log(tmp_path)
    assert "decision=-" in line and "slow=resolve:3.500" in line


def test_a_log_that_cannot_be_written_is_ignored(tmp_path: Path) -> None:
    hook_timing.begin(0.0)
    hook_timing.write(tmp_path, "stop", "claude")  # no state folder: nothing is created
    assert not state.state_dir(tmp_path).exists()

    (state.state_dir(tmp_path) / hook_timing.LOG_NAME).mkdir(parents=True)
    hook_timing.write(tmp_path, "stop", "claude")  # a folder in the log's place


def test_every_hook_event_writes_its_line(tmp_path: Path) -> None:
    decisions.begin(tmp_path, "d1", "Continue?", ("Continue", "Stop"), "chat")

    native(tmp_path, "prompt", {"prompt": "continue"})
    native(tmp_path, "stop", {})

    first, second = _log(tmp_path)
    assert "event=prompt" in first and "decision=d1" in first
    assert "event=stop" in second
