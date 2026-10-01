"""Translate Codex PreToolUse events to the harness policy contract."""

from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event


def parse_codex_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    return parse_policy_event("codex", payload, project_root)


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
