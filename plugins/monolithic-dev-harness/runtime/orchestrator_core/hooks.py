from __future__ import annotations

from pathlib import Path

from .state import Event, QueueState, TaskState


def cli_ui_hook(state: QueueState, event: Event, stream) -> None:
    if event.payload and "task_id" in event.payload:
        task_id = event.payload["task_id"]
        task = state.tasks.get(task_id)
        if task:
            print(f"[*] {event.type}: task [{task_id}] → {task.state.value}")


def authorization_hook(state: QueueState, event: Event, stream) -> None:
    if event.type != "TaskFailedEvent":
        return
    task_id = event.payload.get("task_id")
    task = state.tasks.get(task_id) if task_id else None
    if not task or task.state != TaskState.BLOCKED_REQUIRES_REVIEW:
        return
    print(f"\n[!] Circuit breaker tripped for task '{task_id}'.")
    print("[!] Type 'IMPLEMENTATION APPROVED' to reset retries and resume.")
    try:
        user_input = input("> ")
    except EOFError:
        user_input = ""
    if user_input.strip() == "IMPLEMENTATION APPROVED":
        stream.dispatch(
            Event(
                type="AuthorizationReceivedEvent",
                payload={"task_id": task_id, "token": user_input.strip()},
            )
        )
