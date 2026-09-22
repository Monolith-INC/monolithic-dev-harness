from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from .contracts import ProgressSignature, progress_signature
from .evaluator import SemanticEvaluator, collect_critiques, legacy_semantic_evaluator
from .exhaustive import assert_never
from .failures import Deterministic, Fatal, Transient, classify
from .hooks import authorization_hook, cli_ui_hook
from .manifests import capabilities_by_name
from .schema import validate_inputs
from .state import Event, QueueState, Task, TaskState
from .stream import OrchestratorStream
from .worker import execute_skill


@dataclass(frozen=True)
class NoPreviousAttempt:
    """Nothing has been produced yet, so nothing can have stalled."""


@dataclass(frozen=True)
class PreviousAttempt:
    """The last attempt, projected onto the fields its contract declared."""

    signature: ProgressSignature
    critiques: tuple[str, ...]


RetryContext = NoPreviousAttempt | PreviousAttempt


def _stalled(
    context: RetryContext, signature: ProgressSignature, critiques: Sequence[str]
) -> bool:
    """True when this attempt reproduced the previous one exactly."""
    match context:
        case NoPreviousAttempt():
            return False
        case PreviousAttempt(previous, complaints):
            return previous == signature and complaints == tuple(critiques)
        case _ as unmatched_context:
            assert_never(unmatched_context)


@dataclass(frozen=True)
class Retry:
    """The task may run again."""


@dataclass(frozen=True)
class Stop:
    """The task is finished for this call; ``state`` is what it settled on."""

    state: str


NextStep = Retry | Stop


def _next_step(task: Task, max_retries: int) -> NextStep:
    """Decide from state alone, after every hook has seen the event.

    An interactive approval runs inside `dispatch` and resets the task to READY
    with a cleared retry count, so an approved task is simply READY again here.
    """
    if task.state == TaskState.READY and task.retry_count < max_retries:
        return Retry()
    return Stop(task.state.value)


@dataclass(frozen=True)
class ToolCallResult:
    ok: bool
    output: dict[str, Any] | None
    error: str | None = None
    task_id: str | None = None
    state: str | None = None

    def to_mcp_content(self) -> list[dict[str, str]]:
        payload = (
            {
                "status": "completed",
                "task_id": self.task_id,
                "output": self.output,
            }
            if self.ok
            else {
                "status": "failed",
                "task_id": self.task_id,
                "state": self.state,
                "error": self.error,
            }
        )
        return [{"type": "text", "text": json.dumps(payload, indent=2)}]


class OrchestratorEngine:
    """Synchronous skill orchestrator: queue events, execute, evaluate, retry."""

    def __init__(
        self,
        skills_dir: str | Path,
        *,
        max_retries: int = 3,
        max_approvals: int = 1,
        interactive: bool = False,
        quiet: bool = False,
        semantic_evaluator: SemanticEvaluator = legacy_semantic_evaluator,
    ):
        self.skills_dir = Path(skills_dir)
        self.max_retries = max_retries
        self.max_approvals = max_approvals
        self.interactive = interactive
        self.quiet = quiet
        self.semantic_evaluator = semantic_evaluator
        self._manifests = capabilities_by_name(self.skills_dir)

    def _subscribe_hooks(self, stream: OrchestratorStream) -> None:
        if not self.quiet:
            stream.subscribe(cli_ui_hook)
        if self.interactive:
            stream.subscribe(
                partial(authorization_hook, max_approvals=self.max_approvals)
            )

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": manifest.name,
                "description": manifest.description,
                "inputSchema": manifest.wire.get("input_schema")
                or {"type": "object", "properties": {}},
            }
            for manifest in self._manifests.values()
        ]

    def run_tool_call(
        self, name: str, arguments: dict[str, Any] | None
    ) -> ToolCallResult:
        arguments = arguments or {}
        manifest = self._manifests.get(name)
        if manifest is None:
            return ToolCallResult(
                ok=False, output=None, error=f"Unknown skill '{name}'"
            )

        input_critiques = validate_inputs(arguments, manifest)
        if input_critiques:
            return ToolCallResult(
                ok=False, output=None, error="; ".join(input_critiques)
            )

        task_id = f"{name}-{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, skill_name=name, inputs=arguments)
        stream = OrchestratorStream(
            QueueState(tasks={task_id: task}), max_retries=self.max_retries
        )
        self._subscribe_hooks(stream)
        stream.dispatch(Event(type="TaskSpawnedEvent", payload={"task_id": task_id}))

        context: RetryContext = NoPreviousAttempt()

        while True:
            current = stream.state.tasks[task_id]
            try:
                run = execute_skill(
                    name,
                    arguments,
                    skills_dir=str(self.skills_dir),
                    manifest=manifest,
                    task=current,
                )
            except Exception as exc:
                # Whether running again could help is a property of the failure,
                # declared by its type. Nothing here reads the message.
                reason = str(exc)
                match classify(exc):
                    case Fatal() | Deterministic():
                        halt = True
                    case Transient():
                        halt = False
                    case _ as unmatched_failure:
                        assert_never(unmatched_failure)

                raised: dict[str, Any] = {"task_id": task_id, "critique": reason}
                if halt:
                    raised = {**raised, "halt": True}
                stream.dispatch(Event(type="TaskFailedEvent", payload=raised))
                # A raise produced no result, so the comparison sequence restarts.
                context = NoPreviousAttempt()

                match _next_step(stream.state.tasks[task_id], self.max_retries):
                    case Retry():
                        stream.dispatch(
                            Event(type="TaskSpawnedEvent", payload={"task_id": task_id})
                        )
                        continue
                    case Stop(state):
                        return ToolCallResult(
                            ok=False,
                            output=None,
                            error=reason,
                            task_id=task_id,
                            state=state,
                        )
                    case _ as unmatched_step:
                        assert_never(unmatched_step)

            # Only the work is evaluated and compared. The reflection state and
            # the worker's envelope change on every attempt by design.
            critiques = collect_critiques(
                run.product,
                manifest,
                semantic_evaluator=self.semantic_evaluator,
            )
            output = run.to_wire()
            if not critiques:
                stream.dispatch(
                    Event(
                        type="TaskCompletedEvent",
                        payload={"task_id": task_id, "output": output},
                    )
                )
                return ToolCallResult(
                    ok=True,
                    output=output,
                    task_id=task_id,
                    state=TaskState.COMPLETED.value,
                )

            signature = progress_signature(run.product, manifest.outputs)
            stalled = _stalled(context, signature, critiques)
            failure: dict[str, Any] = {
                "task_id": task_id,
                "critique": "; ".join(critiques),
            }
            if stalled:
                failure = {**failure, "halt": True}
            stream.dispatch(Event(type="TaskFailedEvent", payload=failure))

            # A stall that an operator then approves must not re-detect itself on
            # the next attempt, or the approval would be a no-op.
            context = (
                NoPreviousAttempt()
                if stalled
                else PreviousAttempt(signature, tuple(critiques))
            )

            match _next_step(stream.state.tasks[task_id], self.max_retries):
                case Retry():
                    stream.dispatch(
                        Event(type="TaskSpawnedEvent", payload={"task_id": task_id})
                    )
                    continue
                case Stop(state):
                    return ToolCallResult(
                        ok=False,
                        output=output,
                        error="; ".join(critiques),
                        task_id=task_id,
                        state=state,
                    )
                case _ as unmatched_step:
                    assert_never(unmatched_step)
