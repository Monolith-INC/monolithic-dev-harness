from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_claude_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    tool_call = payload.get("toolCall") or payload.get("tool_call") or {}
    tool_input = (
        tool_call.get("args")
        or tool_call.get("input")
        or payload.get("tool_input")
        or payload.get("arguments")
        or {}
    )
    tool_name = (
        tool_call.get("name")
        or payload.get("tool_name")
        or payload.get("tool")
        or payload.get("name")
        or ""
    )
    command = tool_input.get("CommandLine") or tool_input.get("command")
    file_path = (
        tool_input.get("AbsolutePath")
        or tool_input.get("TargetFile")
        or tool_input.get("path")
        or tool_input.get("file")
        or tool_input.get("file_path")
    )
    return CanonicalToolEvent(
        client="claude",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        workspace_root=project_root,
    )


def format_claude_decision(decision: PolicyDecision) -> dict[str, Any]:
    hook_output = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny" if decision.is_denied() else "allow",
    }
    if decision.is_denied() and decision.reason:
        hook_output["permissionDecisionReason"] = decision.reason
    return {"hookSpecificOutput": hook_output}
