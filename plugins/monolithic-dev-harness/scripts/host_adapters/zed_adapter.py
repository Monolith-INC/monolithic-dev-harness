"""Translate Zed editor-agent events to the harness policy contract.

Zed has no hook lifecycle today, so nothing calls this adapter from a live host yet. It
exists so a future Zed hook mechanism (or an ACP-wrapped external agent that reports tool
calls) drops into the same contract without a rewrite, and so the decision/CLI surfaces can
name `zed` as a first-class host.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event
from .subagents import SubagentOps, unsupported_ops


def parse_zed_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    event = parse_policy_event("zed", payload, project_root)
    return replace(event, host_session_id=zed_session_id(payload))


def zed_session_id(payload: dict[str, Any]) -> str:
    """Zed exposes no thread id to MCP servers; a handle cannot yet be tied to a conversation.

    A Zed worktree env var is a stable *project* anchor, not a session, so this stays empty
    (same limitation the cursor host documents in hosts/cursor.json).
    """
    value = payload.get("session_id")
    return value.strip() if isinstance(value, str) else ""


def format_zed_decision(decision: PolicyDecision) -> dict[str, Any]:
    """Zed has no PreToolUse response channel; a deny is advisory for a future hook only."""
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
    """Nothing verified yet (see `hosts/zed.json`), so every operation is unsupported."""
    return unsupported_ops("zed")
