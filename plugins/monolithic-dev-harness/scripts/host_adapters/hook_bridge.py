"""Translate native hook payloads and responses at the host boundary."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from core.result import Failure, Ok, Result, attempt, bind, err, map_failure
from harness.rules import Decision, ToolCall, make_call
from policy.events import CanonicalToolEvent, PolicyDecision

_SHELL_NAMES = frozenset(
    {
        "Bash",
        "Shell",
        "run_terminal_cmd",
        "shell",
        "run_command",
        "run_shell_command",
        "exec_command",
        "functions.exec_command",
        "functionsexec_command",
    }
)
_EDIT_NAMES = frozenset(
    {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "StrReplace",
        "Delete",
        "edit_file",
        "write",
        "delete_file",
        "search_replace",
        "apply_patch",
        "functionsapply_patch",
        "functions.apply_patch",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    }
)
_READ_NAMES = frozenset(
    {
        "Read",
        "Glob",
        "Grep",
        "LS",
        "WebSearch",
        "WebFetch",
        "read_file",
        "list_dir",
        "grep_search",
        "file_search",
        "codebase_search",
        "ToolSearch",
    }
)
_PATH_KEYS = (
    "file_path",
    "path",
    "notebook_path",
    "target_file",
    "TargetFile",
    "AbsolutePath",
    "file",
)
_PATCH_PATH = re.compile(r"\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)")
_PROJECT_ENV = {
    "claude": "CLAUDE_PROJECT_DIR",
    "cursor": "CURSOR_PROJECT_DIR",
    "codex": "CODEX_PROJECT_ROOT",
    "zed": "ZED_WORKTREE_ROOT",
}


def project_root_hint(host: str) -> str:
    return os.environ.get(_PROJECT_ENV.get(host, ""), "").strip()


def workspace_candidates(host: str, payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        payload.get("cwd"),
        *(payload.get("workspace_roots") or ()),
        project_root_hint(host),
        os.getcwd(),
    )


def _arguments(host: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    match (host, event):
        case ("cursor", "shell"):
            return {"command": payload.get("command", "")}
        case ("claude", _) if isinstance(
            payload.get("toolCall") or payload.get("tool_call"), dict
        ):
            nested = payload.get("toolCall") or payload.get("tool_call") or {}
            return (
                nested.get("args")
                or nested.get("input")
                or payload.get("tool_input")
                or {}
            )
        case _:
            candidate = next(
                (
                    payload[key]
                    for key in ("tool_input", "toolInput", "input", "arguments")
                    if payload.get(key)
                ),
                {},
            )
            match candidate:
                case dict():
                    return candidate
                case str():
                    try:
                        decoded = json.loads(candidate)
                        return (
                            decoded if isinstance(decoded, dict) else {"raw": candidate}
                        )
                    except json.JSONDecodeError:
                        return {"raw": candidate}
                case _:
                    return {}


def _tool_name(host: str, event: str, payload: dict[str, Any]) -> str:
    return (
        "Shell"
        if (host, event) == ("cursor", "shell")
        else str(
            next(
                (
                    value
                    for value in (
                        (payload.get("toolCall") or payload.get("tool_call") or {}).get(
                            "name"
                        )
                        if host == "claude"
                        else None,
                        *(
                            payload.get(key)
                            for key in ("tool_name", "toolName", "tool", "name")
                        ),
                    )
                    if value
                ),
                "",
            )
        )
    )


def _logical_name(raw_name: str, server: str) -> tuple[str, str]:
    parts = raw_name.split("__")
    return (
        ("__".join(parts[2:]).rsplit("/", 1)[-1], server or parts[1])
        if raw_name.startswith("mcp__") and len(parts) >= 3
        else (raw_name, server)
    )


def _kind(raw_name: str, server: str) -> str:
    return (
        "mcp"
        if server
        else "shell"
        if raw_name in _SHELL_NAMES
        else "edit"
        if raw_name in _EDIT_NAMES
        else "read"
        if raw_name in _READ_NAMES
        else "other"
    )


def _patch_targets(patch: str) -> list[str]:
    # Codex trims each patch line before reading a header, so indented, CRLF, and
    # trailing-space headers still apply; read them the same way.
    return [
        match.group(1).strip()
        for line in patch.splitlines()
        if (match := _PATCH_PATH.match(line.strip()))
    ]


def _paths(raw_name: str, arguments: dict[str, Any], cwd: str) -> tuple[str, ...]:
    named = tuple(
        value
        for key in _PATH_KEYS
        if isinstance(value := arguments.get(key), str) and value
    )
    patch = (
        tuple(
            str(Path(cwd) / path) if cwd and not Path(path).is_absolute() else path
            for field in ("command", "patch")
            for path in _patch_targets(str(arguments.get(field) or ""))
        )
        if raw_name in {"apply_patch", "functions.apply_patch", "functionsapply_patch"}
        else ()
    )
    return (*named, *patch)


def parse_tool_call(host: str, event: str, payload: dict[str, Any]) -> ToolCall:
    arguments = _arguments(host, event, payload)
    raw_name = _tool_name(host, event, payload)
    name, server = _logical_name(
        raw_name, str(payload.get("server") or payload.get("server_name") or "")
    )
    command = (
        arguments.get("command")
        or arguments.get("cmd")
        or arguments.get("CommandLine")
        or ""
    )
    cwd = str(payload.get("cwd") or "")
    kind = _kind(raw_name, server)
    return make_call(
        name if kind in {"mcp", "other"} else kind,
        arguments,
        server,
        cwd,
        kind=kind,
        command=command if isinstance(command, str) else "",
        file_paths=_paths(raw_name, arguments, cwd),
    )


def parse_policy_event(
    host: str, payload: dict[str, Any], project_root: str
) -> CanonicalToolEvent:
    call = parse_tool_call(host, "pre-tool", payload)
    return CanonicalToolEvent(
        client=host,
        tool_name=call.name,
        kind=call.kind,
        command=call.command,
        file_path=next(iter(call.file_paths), None),
        file_paths=call.file_paths,
        arguments=call.tool_input,
        workspace_root=project_root,
    )


def format_pre_tool(host: str, decision: Decision) -> str | None:
    from .claude_adapter import format_claude_decision
    from .codex_adapter import format_codex_decision
    from .cursor_adapter import format_cursor_decision
    from .kimi_adapter import format_kimi_decision

    policy = (
        PolicyDecision.allow()
        if decision.allowed
        else PolicyDecision.deny(decision.reason or "")
    )
    formatter = {
        "claude": format_claude_decision,
        "cursor": format_cursor_decision,
        "codex": format_codex_decision,
        "kimi": format_kimi_decision,
    }[host]
    return (
        json.dumps(formatter(policy))
        if host == "cursor" or not decision.allowed
        else None
    )


def prompt_text(payload: dict[str, Any]) -> str:
    return str(payload.get("prompt") or payload.get("user_prompt") or "")


def stop_message(payload: dict[str, Any]) -> str | None:
    """The agent's final message for this turn, or None when the host does not supply it or a
    stop hook already sent the agent back once this turn (never loop)."""
    if payload.get("stop_hook_active") or payload.get("loop_count"):
        return None
    match payload.get("last_assistant_message"):
        case str() as message:
            return message
        case _:
            return None


def format_stop(reason: str) -> str:
    """Claude and Codex both continue the turn on `decision: block` with a reason."""
    return json.dumps({"decision": "block", "reason": reason})


# Hosts whose hook output can carry a line the host shows to the user, beside the context the agent
# reads. Claude Code and Codex document `systemMessage` for every hook event. Cursor shows
# `user_message` only when it denies a call, so a repair on an allowed call has nowhere to go there;
# Kimi and Zed document no such field.
USER_NOTICE_HOSTS = frozenset({"claude", "codex"})


def reaches_user(host: str) -> bool:
    return host in USER_NOTICE_HOSTS


def format_pre_tool_notice(note: str, shown: str = "") -> str:
    """An allowed tool call's note for the agent: context only, no permission decision. `shown` is
    the part the host also shows the user."""
    return json.dumps(
        {
            **({"systemMessage": shown} if shown else {}),
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": note,
            },
        }
    )


def with_user_notice(output: str, shown: str) -> str:
    """A hook's output with `shown` added as the line the host shows the user.

    A hook prints one JSON object or nothing. Nothing becomes a line alone. Output that is not one
    JSON object is left as it is: the line is never worth breaking the host's reply for.
    """
    if not output.strip():
        return json.dumps({"systemMessage": shown}) + "\n"
    try:
        payload = json.loads(output)
    except ValueError:
        return output
    if not isinstance(payload, dict):
        return output
    earlier = payload.get("systemMessage")
    lines = [earlier, shown] if isinstance(earlier, str) and earlier else [shown]
    return json.dumps({**payload, "systemMessage": "\n".join(lines)}) + "\n"


def format_prompt(
    host: str, notes: list[str], mode_notes: Sequence[str] = ()
) -> str | None:
    """What a prompt hook prints. `mode_notes` are what the mode machinery has to say; the user is
    shown those and nothing else, while the agent reads them with the rest."""
    context = "\n".join([*mode_notes, *notes])
    shown = "\n".join(mode_notes) if reaches_user(host) else ""
    match host, context:
        case "cursor", _:
            return json.dumps({"continue": True})
        case _, "":
            return None
        case _ if host == "codex" or shown:
            return json.dumps(
                {
                    **({"systemMessage": shown} if shown else {}),
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": context,
                    },
                }
            )
        case _:
            return context


def delegates_workflow_policy(host: str, event: str) -> bool:
    return host in {"claude", "codex"} or event == "pre-tool"


def should_emit_allow(host: str) -> bool:
    return host == "cursor"


def question_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input")
    return value if isinstance(value, dict) else {}


def question_id(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_use_id") or "")


def answer_response(payload: dict[str, Any]) -> Result[dict[str, Any] | None]:
    """Codex function outputs are JSON text; Claude may supply an object already."""
    match payload.get("tool_response"):
        case str() as serialized:
            return bind(
                map_failure(
                    attempt(
                        lambda: json.loads(serialized),
                        "answer_capture_invalid",
                        "question response",
                        ValueError,
                    ),
                    lambda _: Failure(
                        "answer_capture_invalid", "question response is not valid JSON"
                    ),
                ),
                _answer_object,
            )
        case response:
            return _answer_object(response)


def _answer_object(response: Any) -> Result[dict[str, Any] | None]:
    match response:
        case dict() | None:
            return Ok(response)
        case _:
            return err("answer_capture_invalid", "question response must be an object")


def format_answer_context(note: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": note,
            }
        }
    )
