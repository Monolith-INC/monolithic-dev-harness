from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_cursor_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    tool_name = (
        payload.get("tool_name") or payload.get("toolName") or payload.get("tool") or ""
    )
    tool_input = (
        payload.get("tool_input")
        or payload.get("toolInput")
        or payload.get("input")
        or payload.get("arguments")
        or {}
    )
    command = tool_input.get("command") or tool_input.get("CommandLine") or ""
    file_path = (
        tool_input.get("path")
        or tool_input.get("file")
        or tool_input.get("AbsolutePath")
        or tool_input.get("TargetFile")
    )
    normalized_tool = str(tool_name)
    return CanonicalToolEvent(
        client="cursor",
        tool_name=normalized_tool,
        command=command,
        file_path=file_path,
        workspace_root=project_root,
    )


def format_cursor_decision(decision: PolicyDecision) -> dict[str, Any]:
    if decision.is_denied():
        response: dict[str, Any] = {"permission": "deny"}
        if decision.reason:
            response["agent_message"] = decision.reason
            response["user_message"] = decision.reason
        return response
    return {"permission": "allow"}
