from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event


def parse_cursor_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    return parse_policy_event("cursor", payload, project_root)


def format_cursor_decision(decision: PolicyDecision) -> dict[str, Any]:
    if decision.is_denied():
        response: dict[str, Any] = {"permission": "deny"}
        if decision.reason:
            response["agent_message"] = decision.reason
            response["user_message"] = decision.reason
        return response
    return {"permission": "allow"}
