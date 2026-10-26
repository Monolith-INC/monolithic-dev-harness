"""Codex translation into the shared process channel; no harness policy lives here."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, bind, err, fmap, require
from harness import decisions, process_commands, project_paths, rules, settings
from harness.process_assignment import authorize_call, authorize_model
from harness.process_bus import get_record, local_bus
from harness.process_messages import Context, Origin, assign, cancel, status_update
from host_adapters import (
    codex_bindings,
    codex_runtime,
    hook_bridge,
    work_session_context,
)


def is_subagent(payload: dict[str, Any]) -> bool:
    return codex_bindings.is_child(payload)


def context(repo: Path, payload: dict[str, Any]) -> Result[Context]:
    match payload.get("session_id"), payload.get("cwd"), is_subagent(payload):
        case str() as native, str() as cwd, False if (
            native.strip() and project_paths.root(Path(cwd)) == repo.resolve()
        ):
            return bind(
                work_session_context.resolve_session(repo, "codex", native.strip()),
                lambda scope: (
                    Ok(Context("codex", native.strip(), scope))
                    if scope
                    else err(
                        "process_scope_missing",
                        "the main agent has no bound work session",
                    )
                ),
            )
        case _:
            return err(
                "process_identity_missing",
                "cancellation needs the main agent's native identity and owning project",
            )


def cli_context(repo: Path, native_session_id: str | None = None) -> Result[Context]:
    return context(
        repo,
        {
            "session_id": native_session_id
            if native_session_id is not None
            else os.environ.get("CODEX_THREAD_ID", ""),
            "cwd": str(repo.resolve()),
        },
    )


def before_tool(
    repo: Path, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    match is_subagent(payload), payload.get("hook_event_name"):
        case True, "PreToolUse":
            codex_bindings.observe_child_turn(repo, payload)
        case _:
            pass
    match codex_bindings.guard(repo, payload, call):
        case rules.Decision() as denied:
            return denied
        case _:
            match is_subagent(payload):
                case True:
                    return None
                case False:
                    return _control(repo, payload, call)


def authorize_tool(
    repo: Path, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    match is_subagent(payload):
        case False:
            return None
        case _:
            return _assignment_guard(repo, payload, call)


def event_name(name: str, payload: dict[str, Any]) -> str:
    match name, str(payload.get("tool_name", "")).removeprefix("functions."):
        case "pre-tool", "request_user_input" | "request_user_input_async":
            return "ask"
        case _:
            return name


def _assignment_guard(
    repo: Path, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    return _decision(
        bind(
            work_session_context.resolve_session(
                repo, "codex", str(payload.get("session_id", ""))
            ),
            lambda scope: bind(
                get_record(
                    repo,
                    Context("codex", str(payload.get("session_id", "")), scope or ""),
                    str(payload.get("agent_id", "")),
                ),
                lambda record: _assignment_effect(repo, payload, call, record),
            ),
        )
    )


def _assignment_effect(
    repo: Path, payload: dict[str, Any], call: rules.ToolCall, record: Any
) -> Result[object]:
    match record.assignment:
        case None:
            return err(
                "process_assignment_missing",
                "subagent requires a main-agent assignment before using tools",
            )
        case assignment:
            return bind(
                authorize_model(assignment, str(payload.get("model", ""))),
                lambda verified: _authorized_call(repo, verified, call, record),
            )


def _authorized_call(
    repo: Path, assignment: Any, call: rules.ToolCall, record: Any
) -> Result[object]:
    match authorize_call(repo, assignment, call):
        case rules.Decision() as denied:
            return err(
                denied.rule or "assignment-policy",
                denied.reason or "assignment denied",
            )
        case _:
            return Ok(record)


def _control(
    repo: Path, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    match process_commands.control(call, repo):
        case Err(failure):
            return rules.Decision.deny(failure.code, failure.message)
        case Ok(None):
            return None
        case Ok(intent):
            return _decision(
                bind(
                    context(repo, payload),
                    lambda ctx: bind(
                        require(
                            (
                                not intent.session_id
                                or intent.session_id == ctx.work_session_id
                            )
                            and (not intent.adapter or intent.adapter == ctx.adapter),
                            "process_scope_mismatch",
                            "cancellation names another adapter or work session",
                        ),
                        lambda _: bind(
                            require(
                                isinstance(payload.get("tool_use_id"), str)
                                and bool(payload["tool_use_id"].strip()),
                                "process_identity_missing",
                                "cancellation requires an authentic tool-use identifier",
                            ),
                            lambda _: _publish_control(
                                repo, ctx, intent, payload["tool_use_id"]
                            ),
                        ),
                    ),
                )
            )


def _publish_control(
    repo: Path, ctx: Context, intent: process_commands.ControlRequest, tool_id: str
) -> Result[object]:
    return bind(
        get_record(repo, ctx, intent.process_id),
        lambda record: _control_message(repo, ctx, intent, tool_id, record),
    )


def _control_message(
    repo: Path,
    ctx: Context,
    intent: process_commands.ControlRequest,
    tool_id: str,
    record: Any,
) -> Result[object]:
    match intent.operation:
        case "assign" if intent.assignment is not None:
            return local_bus(repo).request(
                assign(
                    ctx,
                    intent.process_id,
                    intent.assignment,
                    hashlib.sha256(
                        json.dumps((ctx.owner_id, intent.process_id, tool_id)).encode()
                    ).hexdigest(),
                    record.revision,
                ),
                ctx,
            )
        case "cancel" if record.revoked:
            return Ok(record)
        case "cancel":
            return local_bus(repo).request(
                cancel(
                    ctx,
                    intent.process_id,
                    hashlib.sha256(
                        json.dumps((ctx.owner_id, intent.process_id, tool_id)).encode()
                    ).hexdigest(),
                    record.revision,
                ),
                ctx,
            )
        case "report" if record.reported_status == intent.status:
            return Ok(record)
        case "report":
            return local_bus(repo).request(
                status_update(
                    ctx,
                    intent.process_id,
                    record.execution_id,
                    intent.status,
                    hashlib.sha256(
                        json.dumps((ctx.owner_id, intent.process_id, tool_id)).encode()
                    ).hexdigest(),
                    record.revision,
                    Origin.AGENT,
                ),
                ctx,
            )
        case _:
            return err("invalid_process_command", "unknown process operation")


def _decision(result: Result[object]) -> rules.Decision | None:
    match result:
        case Err(failure):
            return rules.Decision.deny(failure.code, failure.message)
        case Ok():
            return None


def event(
    repo: Path, name: str, payload: dict[str, Any]
) -> Result[tuple[bool, str | None]]:
    match name:
        case "subagent-start" | "subagent-stop" | "interrupt" if not settings.governed(
            repo
        ):
            return Ok((True, None))
        case "interrupt":
            return fmap(codex_bindings.interrupt(repo, payload), lambda _: (True, None))
        case "subagent-start" | "subagent-stop":
            return fmap(
                codex_bindings.observe_lifecycle(repo, payload), lambda _: (True, None)
            )
        case "prompt" | "ask" | "answer" | "startup" if is_subagent(payload):
            return Ok((True, _authority_output(name)))
        case "pre-tool" | "ask" | "prompt" if (
            not is_subagent(payload)
            and payload.get("session_id")
            and (settings.governed(repo) or decisions.record(repo) is not None)
        ):
            match codex_runtime.persist_observation(repo, payload):
                case Err(failure):
                    return Ok(
                        (
                            True,
                            hook_bridge.format_prompt("codex", [failure.message])
                            if name == "prompt"
                            else hook_bridge.format_pre_tool(
                                "codex",
                                rules.Decision.deny(failure.code, failure.message),
                            ),
                        )
                    )
                case _:
                    return Ok((False, None))
        case _:
            return Ok((False, None))


def _authority_output(name: str) -> str | None:
    match name:
        case "prompt":
            return hook_bridge.format_prompt(
                "codex",
                [
                    "[harness] subagents return human decision and conversation-binding needs to the main agent; no human authority was recorded"
                ],
            )
        case "answer" | "startup":
            return hook_bridge.format_answer_context(
                "[harness] subagents return human decision and conversation-binding needs to the main agent; no human authority was recorded"
            )
        case _:
            return hook_bridge.format_pre_tool(
                "codex",
                rules.Decision.deny(
                    "codex-child-authority",
                    "subagents return human decisions and work-session controls to the main agent",
                ),
            )


def active() -> bool:
    return bool(os.environ.get("CODEX_THREAD_ID"))
