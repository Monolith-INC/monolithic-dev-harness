"""The mode-scoped hooks. Each runs only while a mode is active and its manifest lists its id.

`orient` gives the prompt the mode's rules and, for a mode with steps, the step its work is at.
`operations` refuses a gateway tool the mode does not list; every other tool is left to the rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.result import Err, Ok, attempt

from . import modes, routing, rules

GATEWAY_SERVER = "workflow-integrations"


@dataclass(frozen=True)
class Orientation:
    """What the prompt hook has from the mode: its rules for the agent, or one line saying it
    could not give them, for the agent and the user."""

    text: str | None = None
    notice: str = ""


def orient(repo: Path) -> Orientation:
    """The mode's rules for the prompt, with the step its work is at.

    Guidance only: when it cannot be given, the prompt goes on without it and says so, so a mode
    never stops the approvals and revokes the same prompt carries.
    """
    match _hooked(repo, "orient"):
        case None:
            return Orientation()
        case active:
            return _oriented(repo, active)


def _oriented(repo: Path, active: modes.Active) -> Orientation:
    mode = active.manifest
    match attempt(
        lambda: (mode.root / "rules.md").read_text(encoding="utf-8"),
        "orient_failed",
        "mode rules unavailable",
        OSError,
        ValueError,
    ):
        case Ok(text):
            head = f"[harness] mode: {mode.name}."
            step = _step(repo, active)
            return Orientation(
                f"{head}\n{step}\nRules:\n{text}" if step else f"{head} Rules:\n{text}"
            )
        case _:
            return Orientation(
                notice=f"The {mode.name} mode's rules could not be read, so this prompt "
                "carries none of them."
            )


def _step(repo: Path, active: modes.Active) -> str:
    """The line saying where the mode's work stands, or one saying it could not be read. A mode
    with no steps has none. Never raises: a tracker that does not answer costs the prompt a line,
    not its approvals."""
    if not routing.routed(active.mode):
        return ""
    match attempt(
        lambda: routing.current(repo, active), "step_unread", "reading the step failed"
    ):
        case Ok(Ok(found)):
            return f"Current step: {routing.describe(found)}"
        case Ok(Err(failure)) | Err(failure):
            return f"Current step: could not be read ({_one_line(failure.message)})."


def _one_line(message: str) -> str:
    return " ".join(message.split()).rstrip(".")


def operations(call: rules.ToolCall, repo: Path) -> rules.Decision | None:
    if not _gateway(call):
        return None
    match _hooked(repo, "operations"):
        case None:
            return None
        case active if call.name in active.manifest.operations:
            return None
        case active:
            mode = active.manifest
            return rules.Decision.deny(
                "mode-operations",
                f"`{call.name}` is not an operation of the {mode.name} mode, which allows: "
                f"{', '.join(mode.operations)}. Leave the mode to use other tools.",
            )


def _gateway(call: rules.ToolCall) -> bool:
    return call.kind == "mcp" and call.server.endswith(GATEWAY_SERVER)


def _hooked(repo: Path, hook_id: str) -> modes.Active | None:
    """The active mode when its manifest lists `hook_id`; None when no such hook runs.

    A mode that cannot be read or repaired is no mode here: a mode never denies a call because of
    its own broken state.
    """
    match modes.active(repo):
        case modes.Active(manifest=mode) as active if hook_id in mode.hooks:
            return active
        case _:
            return None
