from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event


def parse_claude_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    return parse_policy_event("claude", payload, project_root)


def format_claude_decision(decision: PolicyDecision) -> dict[str, Any]:
    hook_output = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny" if decision.is_denied() else "allow",
    }
    if decision.is_denied() and decision.reason:
        hook_output["permissionDecisionReason"] = decision.reason
    return {"hookSpecificOutput": hook_output}
