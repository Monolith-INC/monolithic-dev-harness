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


def format_codex_decision(decision: PolicyDecision) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if decision.is_denied() else "allow",
            **(
                {"permissionDecisionReason": decision.reason}
                if decision.is_denied() and decision.reason
                else {}
            ),
        }
    }


def subagents() -> SubagentOps:
    """Nothing verified yet (see `hosts/codex.json`), so every operation is unsupported."""
    return unsupported_ops("codex")
