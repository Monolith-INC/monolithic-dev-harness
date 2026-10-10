"""Translate Kimi Code CLI hook events to the harness policy contract.

Verified against the official Kimi Code CLI docs on 2026-10-09
(https://www.kimi-cli.com/en/customization/hooks.html, beta at time of
writing): a hook is a shell command configured as a `[[hooks]]` entry in
`~/.kimi/config.toml` that receives a JSON payload on stdin carrying
`session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`, and
`tool_call_id` for `PreToolUse`. A deny is emitted as the same structured
`hookSpecificOutput.permissionDecision` JSON that Claude and Codex use (exit
code 0), or alternatively as exit code 2 with stderr fed back to the model.
This adapter implements the structured-JSON path.

What remains unverified is on the harness side, not the payload side: no
transport lets the harness start a subagent in a Kimi session from its own
process (see `hosts/kimi.json`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision

from .hook_bridge import parse_policy_event
from .subagents import SubagentOps, unsupported_ops


def parse_kimi_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    event = parse_policy_event("kimi", payload, project_root)
    return replace(event, host_session_id=kimi_session_id(payload))


def kimi_session_id(payload: dict[str, Any]) -> str:
    value = payload.get("session_id")
    return value.strip() if isinstance(value, str) else ""


def format_kimi_decision(decision: PolicyDecision) -> dict[str, Any]:
    """Kimi Code CLI structured PreToolUse reply (exit code 0)."""
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
    """Runtime-internal only (see `hosts/kimi.json`), so every operation is unsupported."""
    return unsupported_ops("kimi")
