from __future__ import annotations

from collections.abc import Callable

from .state import Event, QueueState, Task, TaskState

Reducer = Callable[[QueueState, Event, int], QueueState]


def handle_task_spawned(
    state: QueueState, event: Event, _max_retries: int = 3
) -> QueueState:
    task = _task_for(state, event)
    if task is None or task.state is not TaskState.READY:
        return state
    return _replace_task(state, task.copy_with(state=TaskState.IN_PROGRESS))


def handle_task_completed(
    state: QueueState, event: Event, _max_retries: int = 3
) -> QueueState:
    task = _task_for(state, event)
    if task is None or task.state is not TaskState.IN_PROGRESS:
        return state

    completed_task = task.copy_with(
        state=TaskState.COMPLETED,
        output=event.payload.get("output"),
    )
    new_tasks = dict(state.tasks)
    new_tasks[task.id] = completed_task

    for task_id, candidate in list(new_tasks.items()):
        if candidate.state is not TaskState.BLOCKED:
            continue
        if task.id not in candidate.dependencies:
            continue
        if all(
            dependency in new_tasks
            and new_tasks[dependency].state is TaskState.COMPLETED
            for dependency in candidate.dependencies
        ):
            new_tasks[task_id] = candidate.copy_with(state=TaskState.READY)

    return state.copy_with(tasks=new_tasks)


def handle_task_failed(
    state: QueueState, event: Event, max_retries: int = 3
) -> QueueState:
    task = _task_for(state, event)
    if task is None or task.state is not TaskState.IN_PROGRESS:
        return state

    critique = event.payload.get("critique")
    new_retry_count = task.retry_count + 1
    new_critiques = task.critiques + ((str(critique),) if critique else ())
    new_state = (
        TaskState.BLOCKED_REQUIRES_REVIEW
        if new_retry_count >= max_retries or bool(event.payload.get("halt"))
        else TaskState.READY
    )
    return _replace_task(
        state,
        task.copy_with(
            state=new_state,
            retry_count=new_retry_count,
            critiques=new_critiques,
        ),
    )


def handle_authorization_received(
    state: QueueState, event: Event, _max_retries: int = 3
) -> QueueState:
    task = _task_for(state, event)
    token = event.payload.get("token")
    if (
        task is None
        or task.state is not TaskState.BLOCKED_REQUIRES_REVIEW
        or token != "IMPLEMENTATION APPROVED"
    ):
        return state

    return _replace_task(
        state,
        task.copy_with(state=TaskState.READY, retry_count=0, critiques=()),
    )


_HANDLERS: dict[str, Reducer] = {
    "TaskSpawnedEvent": handle_task_spawned,
    "TaskCompletedEvent": handle_task_completed,
    "TaskFailedEvent": handle_task_failed,
    "AuthorizationReceivedEvent": handle_authorization_received,
}


def reduce_queue_state(
    state: QueueState, event: Event, max_retries: int = 3
) -> QueueState:
    """Apply one transition and append its event exactly once.

    Unknown events, missing tasks, and invalid known transitions are recorded
    no-ops. This keeps audit history deterministic without permitting an invalid
    event to force a task into another state.
    """
    handler = _HANDLERS.get(event.type)
    transitioned = handler(state, event, max_retries) if handler else state
    return transitioned.copy_with(events_history=state.events_history + (event,))


def _task_for(state: QueueState, event: Event) -> Task | None:
    task_id = event.payload.get("task_id")
    return state.tasks.get(task_id) if task_id else None


def _replace_task(state: QueueState, task: Task) -> QueueState:
    tasks = dict(state.tasks)
    tasks[task.id] = task
    return state.copy_with(tasks=tasks)
