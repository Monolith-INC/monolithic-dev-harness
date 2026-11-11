"""The mode-scoped hooks. Each runs only while a mode is active and its manifest lists its id.

`orient` gives the prompt the mode's rules. `operations` refuses a gateway tool the mode does not
list; every other tool is left to the rules.
"""

from __future__ import annotations

from pathlib import Path

from core.result import Err, Ok, attempt

from . import modes, rules

GATEWAY_SERVER = "workflow-integrations"


def orient(repo: Path) -> str | None:
    """The mode's rules for the prompt, or None.

    Guidance only: when it cannot be given, the prompt goes on without it, so a mode never stops
    the approvals and revokes the same prompt carries.
    """
    match attempt(
        lambda: _orientation(repo), "orient_failed", "mode rules unavailable"
    ):
        case Ok(text):
            return text
        case Err(_):
            return None


def _orientation(repo: Path) -> str | None:
    match _hooked(repo, "orient"):
        case None:
            return None
        case mode:
            rules_text = (mode.root / "rules.md").read_text(encoding="utf-8")
            return f"[harness] mode: {mode.name}. Rules:\n{rules_text}"


def operations(call: rules.ToolCall, repo: Path) -> rules.Decision | None:
    if not _gateway(call):
        return None
    match _hooked(repo, "operations"):
        case None:
            return None
        case mode if call.name in mode.operations:
            return None
        case mode:
            return rules.Decision.deny(
                "mode-operations",
                f"`{call.name}` is not an operation of the {mode.name} mode, which allows: "
                f"{', '.join(mode.operations)}. Leave the mode to use other tools.",
            )


def _gateway(call: rules.ToolCall) -> bool:
    return call.kind == "mcp" and call.server.endswith(GATEWAY_SERVER)


def _hooked(repo: Path, hook_id: str) -> modes.Mode | None:
    """The active mode when its manifest lists `hook_id`; None when no such hook runs.

    A mode that cannot be read or repaired is no mode here: a mode never denies a call because of
    its own broken state.
    """
    match modes.active(repo):
        case modes.Active(manifest=mode) if hook_id in mode.hooks:
            return mode
        case _:
            return None
