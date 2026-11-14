"""The time every hook event may spend, counted from the moment its process started.

The hosts cancel a hook at their own limit (15 s before a tool call, 10 s for the others) and treat
a cancelled hook as if it had said nothing. A question shown that way loses its answer silently.
So each event stops itself a few seconds earlier and says what happened instead.

With `SIGALRM` a timer interrupts the event wherever it is. Without it (Windows) the event checks
the clock at each of its steps. Once an event starts recording an answer (`commit`), it is never cut
off again: the answer and what it opens are written together, or not at all.

A timeout is counted per decision, so the way out it names changes with each repeat and the agent
is never sent round the same loop twice.
"""

from __future__ import annotations

import contextlib
import signal
import threading
import time
from collections.abc import Callable
from typing import Any

from harness import hook_timing, state

# Seconds from process start; each leaves about three seconds of the host's limit.
PRE_TOOL_SECONDS = 12.0
OTHER_SECONDS = 7.0
PRE_TOOL_EVENTS = frozenset(("pre-tool", "shell", "mcp"))
COUNTER_NAME = "hook-timeouts.json"
# Timeouts further apart than this are not repeats of each other.
REPEAT_WINDOW_SECONDS = 15 * 60

_run: dict[str, Any] = {"deadline": float("inf"), "committed": False}


class OutOfTime(BaseException):
    """Not an Exception, so no `except Exception` on the way can swallow it and let a call run."""


def budget(event: str) -> float:
    return PRE_TOOL_SECONDS if event in PRE_TOOL_EVENTS else OTHER_SECONDS


def _alarm(_signum: int, _frame: Any) -> None:
    match _run["committed"]:
        case True:
            return
        case False:
            raise OutOfTime("the hook ran out of time")


def check() -> None:
    """Between steps: stop here when the budget is spent, unless the event has committed."""
    match time.monotonic() >= _run["deadline"] and not _run["committed"]:
        case True:
            raise OutOfTime("the hook ran out of time")
        case False:
            return


def step(name: str) -> None:
    """Close a timed step (`hook_timing.step`), then check the budget."""
    hook_timing.step(name)
    check()


def commit() -> None:
    """From here on the event finishes, even past its budget: it is about to record an answer,
    and an answer recorded without what it opens (or the reverse) would be lost. What follows is
    local file work only."""
    _run["committed"] = True


def run(
    event: str,
    started: float,
    handler: Callable[[], int],
    on_timeout: Callable[[], int],
) -> int:
    """Run `handler` within the event's budget, counted from `started` (`time.monotonic()`)."""
    deadline = started + budget(event)
    _run.update(deadline=deadline, committed=False)
    timed = (
        hasattr(signal, "SIGALRM")
        and threading.current_thread() is threading.main_thread()
    )
    try:
        if timed:
            signal.signal(signal.SIGALRM, _alarm)
            signal.setitimer(
                signal.ITIMER_REAL, max(deadline - time.monotonic(), 0.001)
            )
        check()
        return handler()
    except OutOfTime:
        # The timer is stopped first, so it cannot cut off the timeout's own message.
        _stop(timed)
        return on_timeout()
    finally:
        _stop(timed)
        _run.update(deadline=float("inf"), committed=False)


def _stop(timed: bool) -> None:
    # Committed first, so an alarm landing before the timer is cleared does nothing.
    _run["committed"] = True
    if timed:
        signal.setitimer(signal.ITIMER_REAL, 0)


def count_timeout(repo: Any, decision: str) -> int:
    """Add one timeout for this decision and return how many it has had in a row. A run of
    timeouts ends after `REPEAT_WINDOW_SECONDS` without one. A counter that cannot be read or
    written counts as the first, so the gentlest way out is named."""
    with contextlib.suppress(Exception):
        path = state.state_dir(repo) / COUNTER_NAME
        if not path.parent.is_dir():
            return 1
        now = time.time()
        count = _next_count(state.read_json(path) or {}, decision, now)
        state.write_json(path, {"decision": decision, "count": count, "at": now})
        return count
    return 1


def _next_count(saved: dict[str, Any], decision: str, now: float) -> int:
    match (
        saved.get("decision") == decision
        and now - float(saved.get("at", 0)) < REPEAT_WINDOW_SECONDS
    ):
        case True:
            return int(saved.get("count", 0)) + 1
        case False:
            return 1


def answer_way_out(count: int) -> str:
    """What the agent does after the harness ran out of time recording an answer."""
    match count:
        case 1:
            return (
                "Show the same question again, with the same wording and options; showing it "
                "again is always allowed."
            )
        case 2:
            return (
                "Ask the user to type the number of their choice in the chat. If the question "
                "is not on screen, run `harness decision fallback` with the flags the harness "
                "named before, then ask."
            )
        case _:
            return (
                "The harness cannot record answers right now. Ask the user to send "
                "`harness suspend` as its own message to work without the harness, and say "
                "that the question stays open until it is resumed."
            )


def not_recorded(count: int) -> str:
    """The note for an `answer` or `prompt` event that ran out of time: nothing was recorded."""
    return (
        "[harness hook-budget] The harness ran out of time and did not record this answer. "
        "The question is still open. " + answer_way_out(count)
    )


def not_shown(count: int) -> str:
    """The refusal for an `ask` event that ran out of time before it could register the question."""
    return (
        "The harness ran out of time before it could register this question, so its answer "
        "would be lost. " + answer_way_out(count)
    )
