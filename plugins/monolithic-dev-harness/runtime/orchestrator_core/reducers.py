from __future__ import annotations

from .state import Event, QueueState, TaskState


def handle_task_spawned(state: QueueState, event: Event) -> QueueState:
    task_id = event.payload.get("task_id")
    if not task_id or task_id not in state.tasks:
        return state
    task = state.tasks[task_id]
    new_tasks = dict(state.tasks)
    new_tasks[task_id] = task.copy_with(state=TaskState.IN_PROGRESS)
    return state.copy_with(tasks=new_tasks, events_history=state.events_history + [event])


def handle_task_completed(state: QueueState, event: Event) -> QueueState:
    task_id = event.payload.get("task_id")
    output = event.payload.get("output")
    if not task_id or task_id not in state.tasks:
        return state
    task = state.tasks[task_id]
    new_tasks = dict(state.tasks)
    new_tasks[task_id] = task.copy_with(state=TaskState.COMPLETED, output=output)
    for t_id, t in new_tasks.items():
        if t.state == TaskState.BLOCKED and task_id in t.dependencies:
            all_done = all(
                dep in new_tasks and new_tasks[dep].state == TaskState.COMPLETED
                for dep in t.dependencies
            )
            if all_done:
                new_tasks[t_id] = t.copy_with(state=TaskState.READY)
    return state.copy_with(tasks=new_tasks, events_history=state.events_history + [event])


def handle_task_failed(state: QueueState, event: Event, max_retries: int = 3) -> QueueState:
    task_id = event.payload.get("task_id")
    critique = event.payload.get("critique")
    if not task_id or task_id not in state.tasks:
        return state
    task = state.tasks[task_id]
    new_retry_count = task.retry_count + 1
    new_critiques = task.critiques + ([critique] if critique else [])
    if new_retry_count >= max_retries:
        new_task_state = TaskState.BLOCKED_REQUIRES_REVIEW
    else:
        new_task_state = TaskState.READY
    new_tasks = dict(state.tasks)
    new_tasks[task_id] = task.copy_with(
        state=new_task_state,
        retry_count=new_retry_count,
        critiques=new_critiques,
    )
    return state.copy_with(tasks=new_tasks, events_history=state.events_history + [event])


def handle_authorization_received(state: QueueState, event: Event) -> QueueState:
    task_id = event.payload.get("task_id")
    token = event.payload.get("token")
    if not task_id or task_id not in state.tasks:
        return state
    if token != "IMPLEMENTATION APPROVED":
        return state
    task = state.tasks[task_id]
    if task.state != TaskState.BLOCKED_REQUIRES_REVIEW:
        return state
    new_tasks = dict(state.tasks)
    new_tasks[task_id] = task.copy_with(state=TaskState.READY, retry_count=0, critiques=[])
    return state.copy_with(tasks=new_tasks, events_history=state.events_history + [event])


def reduce_queue_state(state: QueueState, event: Event, max_retries: int = 3) -> QueueState:
    if event.type == "TaskSpawnedEvent":
        return handle_task_spawned(state, event)
    if event.type == "TaskCompletedEvent":
        return handle_task_completed(state, event)
    if event.type == "TaskFailedEvent":
        return handle_task_failed(state, event, max_retries)
    if event.type == "AuthorizationReceivedEvent":
        return handle_authorization_received(state, event)
    return state.copy_with(events_history=state.events_history + [event])
