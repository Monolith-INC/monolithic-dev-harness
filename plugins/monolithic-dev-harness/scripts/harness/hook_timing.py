"""What one hook process spent its time on: one line per event in `.harness/state/hook-timing.log`.

The log is local to the clone, like the rest of the state folder. It is there to be read after a
trial: which event ran, for which decision, how long it took from process start, and the slowest
step when one took over two seconds. Logging never fails or delays a hook: a line that cannot be
written is dropped.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from harness import state

LOG_NAME = "hook-timing.log"
SLOW_STEP_SECONDS = 2.0
# The log starts over past this size, so it never grows without limit.
MAX_BYTES = 1_000_000

_run: dict = {}


def begin(started: float) -> None:
    """Start the clock of this hook process at `started`, a `time.monotonic()` reading."""
    _run.update(started=started, last=started, steps=[], decision="")


begin(time.monotonic())


def elapsed() -> float:
    """Seconds since the hook process started."""
    return time.monotonic() - _run["started"]


def step(name: str) -> None:
    """Close the step that just ran: everything since the previous step, or since the start."""
    now = time.monotonic()
    _run["steps"].append((name, now - _run["last"]))
    _run["last"] = now


def decision(identifier: str) -> None:
    """Name the decision this event is about."""
    _run["decision"] = identifier


def current_decision() -> str:
    """The decision this event named so far, or "" when none yet."""
    return str(_run.get("decision", ""))


def line(event: str, host: str) -> str:
    name, seconds = max(_run["steps"], key=lambda entry: entry[1], default=("", 0.0))
    slow = f" slow={name}:{seconds:.3f}" if seconds > SLOW_STEP_SECONDS else ""
    return (
        f"{datetime.now(UTC).isoformat(timespec='seconds')} event={event} host={host} "
        f"decision={_run['decision'] or '-'} elapsed={elapsed():.3f}{slow}"
    )


def write(repo: Path, event: str, host: str) -> None:
    """Append this event's line. Only where the harness already keeps state, and never raising."""
    try:
        folder = state.state_dir(repo)
        if not folder.is_dir():
            return
        path = folder / LOG_NAME
        mode = "w" if path.exists() and path.stat().st_size > MAX_BYTES else "a"
        with path.open(mode, encoding="utf-8") as log:
            log.write(line(event, host) + "\n")
    except Exception:
        return
