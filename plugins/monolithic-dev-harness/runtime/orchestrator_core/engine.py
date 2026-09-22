from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import build_skill_prompt, critiques_to_error_log
from .artifact_validator import critiques_from_results, validate_artifact
from .handlers import execute_handler
from .hooks import authorization_hook, cli_ui_hook
from .ingest import ingest_file
from .mailbox import clear_error_log, write_error_log, write_prompt
from .manifests import manifest_by_name
from .reflection import load_mistakes
from .report_formatter import format_terminal_report
from .state import Event, QueueState, Task, TaskState
from .stream import OrchestratorStream


@dataclass(frozen=True)
class ToolCallResult:
    ok: bool
    output: dict[str, Any] | None
    error: str | None = None
    task_id: str | None = None
    state: str | None = None

    def to_mcp_content(self) -> list[dict[str, str]]:
        payload = (
            {"status": "completed", "task_id": self.task_id, "output": self.output}
            if self.ok
            else {"status": "failed", "task_id": self.task_id, "state": self.state, "error": self.error}
        )
        return [{"type": "text", "text": json.dumps(payload, indent=2)}]


class OrchestratorEngine:
    def __init__(
        self,
        skills_dir: Path,
        *,
        project_root: Path,
        state_dir: Path,
        max_retries: int = 3,
        interactive: bool = False,
        quiet: bool = False,
    ) -> None:
        self.skills_dir = skills_dir
        self.project_root = project_root
        self.state_dir = state_dir
        self.max_retries = max_retries
        self.interactive = interactive
        self.quiet = quiet
        self._manifests = manifest_by_name(skills_dir)

    def _subscribe_hooks(self, stream: OrchestratorStream) -> None:
        if not self.quiet:
            stream.subscribe(cli_ui_hook)
        if self.interactive:
            stream.subscribe(authorization_hook)

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for manifest in self._manifests.values():
            tools.append(
                {
                    "name": manifest.get("name"),
                    "description": manifest.get("description"),
                    "inputSchema": manifest.get("input_schema") or {"type": "object", "properties": {}},
                }
            )
        return tools

    def run_tool_call(self, name: str, arguments: dict[str, Any] | None) -> ToolCallResult:
        arguments = arguments or {}
        if name not in self._manifests:
            return ToolCallResult(ok=False, output=None, error=f"unknown skill: {name}")

        task_id = f"{name}-{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, skill_name=name, inputs=arguments)
        stream = OrchestratorStream(QueueState(tasks={task_id: task}), max_retries=self.max_retries)
        self._subscribe_hooks(stream)
        stream.dispatch(Event(type="TaskSpawnedEvent", payload={"task_id": task_id}))

        last_critiques: list[str] = []
        last_output: dict[str, Any] | None = None

        while True:
            output = execute_handler(
                name,
                arguments,
                skills_dir=self.skills_dir,
                state_dir=self.state_dir,
            )
            critiques = [c for c in output.get("critiques", []) if c]
            fail_checks = output.get("outcome") == "fail" or output.get("blocked")

            if name == "validate-artifact" and output.get("outcome") == "pass":
                stream.dispatch(
                    Event(type="TaskCompletedEvent", payload={"task_id": task_id, "output": output})
                )
                return ToolCallResult(ok=True, output=output, task_id=task_id, state=TaskState.COMPLETED.value)

            if name == "auto-fix-artifact":
                if output.get("mode") == "completed" or (not critiques and output.get("mode") != "instructions"):
                    stream.dispatch(
                        Event(type="TaskCompletedEvent", payload={"task_id": task_id, "output": output})
                    )
                    clear_error_log(self.project_root, name)
                    return ToolCallResult(ok=True, output=output, task_id=task_id, state=TaskState.COMPLETED.value)

            if not critiques and output.get("mode") == "instructions":
                stream.dispatch(
                    Event(type="TaskCompletedEvent", payload={"task_id": task_id, "output": output})
                )
                return ToolCallResult(ok=True, output=output, task_id=task_id, state=TaskState.COMPLETED.value)

            if not fail_checks and not critiques:
                stream.dispatch(
                    Event(type="TaskCompletedEvent", payload={"task_id": task_id, "output": output})
                )
                return ToolCallResult(ok=True, output=output, task_id=task_id, state=TaskState.COMPLETED.value)

            critique_blob = "; ".join(critiques) if critiques else output.get("error", "validation failed")
            if critiques == last_critiques and output == last_output:
                stream.dispatch(
                    Event(
                        type="TaskFailedEvent",
                        payload={"task_id": task_id, "critique": critique_blob},
                    )
                )
                task = stream.state.tasks[task_id]
                return ToolCallResult(
                    ok=False,
                    output=output,
                    error="identical critiques across retries — circuit breaker",
                    task_id=task_id,
                    state=task.state.value,
                )

            last_critiques = list(critiques)
            last_output = output
            stream.dispatch(
                Event(type="TaskFailedEvent", payload={"task_id": task_id, "critique": critique_blob})
            )
            task = stream.state.tasks[task_id]

            if task.state == TaskState.BLOCKED_REQUIRES_REVIEW:
                write_error_log(self.project_root, name, critiques_to_error_log(critiques))
                return ToolCallResult(
                    ok=False,
                    output=output,
                    error="circuit breaker tripped — IMPLEMENTATION APPROVED required",
                    task_id=task_id,
                    state=task.state.value,
                )

            reflection = output.get("reflection", {})
            arguments = {
                **arguments,
                "attempt": reflection.get("attempt", task.retry_count),
                "last_critiques": critiques,
            }
            output["prompt"] = self._compile_prompt(name, arguments, output)
            continue

    def _compile_prompt(self, skill_name: str, arguments: dict[str, Any], output: dict[str, Any]) -> str:
        file_path = arguments.get("file_path", "")
        record = None
        if file_path and Path(file_path).is_file():
            record = ingest_file(Path(file_path))
        from .reflection import ReflectionDecision, ReflectionState

        reflection_data = output.get("reflection", {})
        reflection = ReflectionDecision(
            critiques=output.get("critiques", []),
            reflection=ReflectionState(
                attempt=reflection_data.get("attempt", 0),
                last_critiques=tuple(reflection_data.get("last_critiques", [])),
                blocked=reflection_data.get("blocked", False),
            ),
            mode=output.get("mode", "correcao"),
            blocked=output.get("blocked", False),
        )
        mistakes = load_mistakes(self.state_dir, skill_name=skill_name)
        return build_skill_prompt(
            skill_name=skill_name,
            skill_instructions=output.get("instructions", ""),
            mode=output.get("mode", "novo"),
            record=record,
            file_path=file_path or None,
            reflection=reflection,
            mistakes=mistakes,
        )

    def compile_mailbox(self, skill_name: str, *, file_path: str, mode: str = "novo") -> Path:
        output = execute_handler(
            skill_name,
            {"file_path": file_path},
            skills_dir=self.skills_dir,
            state_dir=self.state_dir,
        )
        prompt = build_skill_prompt(
            skill_name=skill_name,
            skill_instructions=output.get("instructions", ""),
            mode=mode,
            file_path=file_path,
            record=ingest_file(Path(file_path)) if Path(file_path).is_file() else None,
            mistakes=load_mistakes(self.state_dir, skill_name=skill_name),
        )
        return write_prompt(self.project_root, skill_name, prompt)

    def evaluate_file(self, file_path: Path, *, skill_name: str = "validate-artifact") -> tuple[bool, str]:
        record = ingest_file(file_path)
        results = validate_artifact(record)
        report = format_terminal_report(record, results)
        critiques = critiques_from_results(results)
        has_failures = any(r.result == "FAIL" for r in results)
        if has_failures:
            write_error_log(self.project_root, skill_name, critiques_to_error_log(critiques))
            return False, report
        clear_error_log(self.project_root, skill_name)
        return True, report
