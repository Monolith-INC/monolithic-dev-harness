from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .state import Event, QueueState, TaskState

if TYPE_CHECKING:  # pragma: no cover - import cycle only exists for typing
    from .stream import OrchestratorStream


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def cli_ui_hook(state: QueueState, event: Event, stream: OrchestratorStream) -> None:
    """Log task transitions to stderr (safe for MCP stdio transport)."""
    _log(f"[*] Event Processed: {event.type}")
    if event.payload and "task_id" in event.payload:
        task_id = event.payload["task_id"]
        if task_id in state.tasks:
            task = state.tasks[task_id]
            _log(f"    Task [{task_id}] is now {task.state.value}")
            if task.state == TaskState.BLOCKED_REQUIRES_REVIEW:
                _log(f"    Critiques length: {len(task.critiques)}")


def _approvals_for(state: QueueState, task_id: str) -> int:
    """Count approvals already granted to this task.

    Derived from the append-only history rather than a counter, so the bound is
    a pure function of state and survives anything that rebuilds the stream.
    """
    return sum(
        1
        for past in state.events_history
        if past.type == "AuthorizationReceivedEvent"
        and past.payload.get("task_id") == task_id
    )


def authorization_hook(
    state: QueueState,
    event: Event,
    stream: OrchestratorStream,
    *,
    max_approvals: int = 1,
) -> None:
    """Halt execution for human review when the circuit breaker trips (interactive mode only).

    An approval restores the task's full retry budget, so an approver that never
    says no would never terminate. The cap belongs here rather than in the
    engine: refusing to prompt leaves the task honestly BLOCKED_REQUIRES_REVIEW,
    where capping downstream would mean discarding an approval already applied
    and reporting a state the task no longer had.
    """
    if event.type != "TaskFailedEvent":
        return

    task_id = event.payload.get("task_id")
    if not isinstance(task_id, str):
        return
    task = state.tasks.get(task_id)
    if not task or task.state != TaskState.BLOCKED_REQUIRES_REVIEW:
        return

    if _approvals_for(state, task_id) >= max_approvals:
        _log(
            f"[-] Approval limit ({max_approvals}) reached for task '{task_id}'. "
            "Task remains blocked."
        )
        return

    _log(f"\n[!] ALERT: Circuit Breaker tripped for task '{task_id}'.")
    _log("[!] The task failed to complete successfully after max retries.")
    _log("Type 'IMPLEMENTATION APPROVED' to authorize new instructions and resume.")

    try:
        user_input = input("> ")
    except EOFError:
        user_input = ""

    if user_input.strip() == "IMPLEMENTATION APPROVED":
        _log(f"[+] Authorization received for task '{task_id}'. Resuming queue...")
        auth_event = Event(
            type="AuthorizationReceivedEvent",
            payload={"task_id": task_id, "token": user_input.strip()},
        )
        stream.dispatch(auth_event)
    else:
        _log("[-] Authorization denied. Task remains blocked.")
