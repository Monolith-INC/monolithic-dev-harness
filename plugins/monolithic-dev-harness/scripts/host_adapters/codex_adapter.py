"""Translate Codex PreToolUse events to the harness policy contract."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event
from .subagents import SubagentOps, unsupported_ops


def parse_codex_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    event = parse_policy_event("codex", payload, project_root)
    return replace(event, host_session_id=codex_session_id(payload))


def codex_session_id(payload: dict[str, Any]) -> str:
    value = payload.get("session_id")
    return value.strip() if isinstance(value, str) else ""


def native_operation(tool_name: str) -> str | None:
    """Native names in the pinned runtime contract; mapping is not execution evidence."""
    return {
        "collaborationspawn_agent": "start",
        "collaborationfollowup_task": "follow-up",
        "collaborationlist_agents": "status",
        "collaborationwait_agent": "wait",
        "collaborationinterrupt_agent": "interrupt",
        "collaborationsend_message": "message",
    }.get(tool_name)


def format_codex_decision(decision: PolicyDecision) -> dict[str, Any]:
    match decision.is_denied():
        case False:
            return {}
        case True:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    **(
                        {"permissionDecisionReason": decision.reason}
                        if decision.reason
                        else {}
                    ),
                }
            }


def subagents() -> SubagentOps:
    """The subprocess contract is unsupported; native workflows use the host tool boundary."""
    return unsupported_ops("codex")


def installation():
    from .installation_layouts import adapter

    return adapter("codex")
