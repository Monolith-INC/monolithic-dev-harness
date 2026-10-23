"""Observed Codex question contracts; availability alone never proves permission.

Profiles describe evidence at the native boundary. They neither authorize an effect nor change
the host mode. The protected observation record deliberately cannot qualify a structured UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap


@dataclass(frozen=True)
class CodexRuntimeProfile:
    surface: str = "unknown"
    mode: str = "unknown"
    root: bool = False
    tools: frozenset[str] = frozenset()
    evidence: tuple[str, ...] = ()
    qualified_transports: frozenset[str] = frozenset()
    default_question_enabled: bool = False
    domain_approval_permitted: bool = False
    async_required_permitted: bool = False


@dataclass(frozen=True)
class DecisionContext:
    kind: str = "required"
    approval: bool = False
    structured_required: bool = True
    purpose: str = "domain"

    @property
    def optional(self) -> bool:
        return self.kind == "preference" and not self.approval


def select_question_transport(
    profile: CodexRuntimeProfile, decision: DecisionContext
) -> Result[str]:
    """Select delivery, without recording an answer or granting approval."""
    match decision.purpose, decision.kind:
        case "host_permission" | "sandbox_escalation", _:
            return err(
                "unsupported_decision_transport",
                "Use the host permission mechanism for sandbox or permission escalation.",
            )
        case "domain", "preference" | "required" | "approval":
            return _select_domain(profile, decision)
        case _:
            return err("unsupported_decision_transport", "Unknown decision contract.")


def _select_domain(
    profile: CodexRuntimeProfile, decision: DecisionContext
) -> Result[str]:
    match profile:
        case CodexRuntimeProfile(root=False, evidence=(_, *_)):
            return err(
                "unsupported_decision_transport",
                "A child must return its decision need to the root; it cannot question the human.",
            )
        case CodexRuntimeProfile(root=True, evidence=(_, *_)) if (
            profile.surface in ("desktop", "cli", "hook")
            and "request_user_input" in profile.tools
            and (
                profile.mode == "plan"
                or (
                    profile.mode == "default"
                    and profile.default_question_enabled
                    and decision.optional
                )
            )
            and (
                decision.optional
                or (
                    "blocking" in profile.qualified_transports
                    and (
                        not (decision.approval or decision.kind == "approval")
                        or profile.domain_approval_permitted
                    )
                )
            )
        ):
            return Ok("blocking")
        case CodexRuntimeProfile(root=True, evidence=(_, *_)) if (
            profile.surface in ("desktop", "cli", "hook")
            and "request_user_input_async" in profile.tools
            and (
                decision.optional
                or (
                    profile.async_required_permitted
                    and (
                        not (decision.approval or decision.kind == "approval")
                        or profile.domain_approval_permitted
                    )
                )
            )
        ):
            return Ok("async")
        case _ if decision.optional or not decision.structured_required:
            return Ok("chat")
        case _:
            return err(
                "unsupported_decision_transport",
                "The observed Codex mode has no permitted, qualified structured transport "
                "for this required decision. Keep it pending; typed recovery does not "
                "qualify the structured control. Use harness decision fallback for the same "
                "typed menu. If the root actually advertises and permits native async input, "
                "invoke that control with this pending decision's exact question and options; "
                "delivery still is not an answer. Plan decisions do not permit implementation "
                "until the host actually switches mode.",
            )


def observed_profile(payload: dict[str, Any]) -> Result[CodexRuntimeProfile]:
    """Normalize only host-originated observations; never call with model-authored events.

    Hook `permission_mode` describes approval policy, not collaboration mode. No current
    hook payload establishes collaboration mode. An observed call is not UI qualification.
    """
    match payload:
        case {"session_id": str() as session} if any(
            payload.get(key) for key in ("agent_id", "agent_type", "parent_thread_id")
        ):
            return Ok(CodexRuntimeProfile(evidence=(session,), root=False))
        case {"session_id": str() as session} if session and not payload.get(
            "parent_thread_id"
        ):
            return Ok(
                CodexRuntimeProfile(
                    surface="hook",
                    mode="unknown",
                    root=True,
                    tools=_observed_tools(payload),
                    evidence=(session, str(payload.get("hook_event_name", "unknown"))),
                    domain_approval_permitted=_async_observed(payload),
                    async_required_permitted=_async_observed(payload),
                )
            )
        case _:
            return err(
                "codex_profile_invalid", "Native Codex session identity is missing."
            )


def persist_observation(repo: Path, payload: dict[str, Any]) -> Result[Path]:
    """Hook-only I/O edge. Every root observation replaces stale Plan evidence."""
    return bind(
        observed_profile(payload),
        lambda profile: _persist_root(repo, payload, profile),
    )


def _observed_tools(payload: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        tool
        for tool in (
            str(payload.get("tool_name", "")),
            *payload.get("observed_tools", ()),
        )
        if tool in ("request_user_input", "request_user_input_async", "clock.sleep")
    )


def _async_observed(payload: dict[str, Any]) -> bool:
    return "request_user_input_async" in _observed_tools(payload) and all(
        isinstance(payload.get(key), str) and payload.get(key)
        for key in ("session_id", "turn_id", "model")
    )


def _record(payload: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    return {
        **{
            key: str(payload.get(key, ""))
            for key in (
                "session_id",
                "turn_id",
                "model",
                "agent_id",
                "parent_thread_id",
                "tool_name",
                "hook_event_name",
            )
        },
        "observed_tools": sorted(
            _observed_tools(payload) | _retained_tools(payload, previous)
        ),
    }


def _retained_tools(
    payload: dict[str, Any], previous: dict[str, Any] | None
) -> frozenset[str]:
    match previous:
        case dict() if all(
            payload.get(key) and payload.get(key) == previous.get(key)
            for key in ("session_id", "turn_id", "model")
        ):
            return _observed_tools(previous)
        case _:
            return frozenset()


def _persist_root(
    repo: Path, payload: dict[str, Any], profile: CodexRuntimeProfile
) -> Result[Path]:
    from harness import state

    match profile.root:
        case False:
            return err(
                "codex_profile_invalid", "A child cannot replace root mode evidence."
            )
        case True:
            return fmap(
                attempt(
                    lambda: state.write_json(
                        repo / ".harness/state/host_sessions/codex/runtime.json",
                        _record(
                            payload,
                            state.read_json(
                                repo / ".harness/state/host_sessions/codex/runtime.json"
                            ),
                        ),
                    ),
                    "codex_profile_unwritable",
                    "Codex runtime observation",
                    OSError,
                ),
                lambda _: repo / ".harness/state/host_sessions/codex/runtime.json",
            )


def load_profile(repo: Path, native_session_id: str) -> CodexRuntimeProfile:
    """Read protected hook evidence only for the exact current native conversation."""
    from harness import state

    match state.read_json(repo / ".harness/state/host_sessions/codex/runtime.json"):
        case {"session_id": str() as session} as payload if (
            native_session_id and session == native_session_id
        ):
            match observed_profile(payload):
                case Ok(profile):
                    return profile
                case _:
                    return CodexRuntimeProfile()
        case _:
            return CodexRuntimeProfile()
