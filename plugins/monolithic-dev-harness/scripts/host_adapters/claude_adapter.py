from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event
from .subagents import SubagentOps, unsupported_ops


def parse_claude_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    event = parse_policy_event("claude", payload, project_root)
    return replace(event, host_session_id=claude_session_id(payload))


def claude_session_id(payload: dict[str, Any]) -> str:
    value = payload.get("session_id")
    return value.strip() if isinstance(value, str) else ""


def format_claude_decision(decision: PolicyDecision) -> dict[str, Any]:
    hook_output = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny" if decision.is_denied() else "allow",
    }
    if decision.is_denied() and decision.reason:
        hook_output["permissionDecisionReason"] = decision.reason
    return {"hookSpecificOutput": hook_output}


def subagents() -> SubagentOps:
    """Nothing verified yet (see `hosts/claude.json`), so every operation is unsupported."""
    return unsupported_ops("claude")


def assistant_text_after(transcript: Path, command: str) -> str:
    """The text Claude wrote to the user after its last tool call whose command contains
    `command`. Tool output is collapsed in the host, so only this text is what the user saw."""
    texts: list[str] = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        content = (row.get("message") or {}).get("content")
        if row.get("type") != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            match block:
                case {"type": "tool_use", "input": {"command": str() as ran}} if (
                    command in ran
                ):
                    texts.clear()
                case {"type": "text", "text": str() as text}:
                    texts.append(text)
                case _:
                    pass
    return "\n".join(texts)
