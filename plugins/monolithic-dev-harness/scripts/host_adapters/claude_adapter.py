from __future__ import annotations

from dataclasses import replace
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
