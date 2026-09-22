from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

PLACEHOLDER_PATTERN = re.compile(
    r"\b(TODO|TBD|FIXME|XXX|\?\?\?|<fill[- ]?in>)\b", re.IGNORECASE
)


@dataclass
class ReflectionState:
    attempt: int = 0
    last_critiques: tuple[str, ...] = ()
    blocked: bool = False
    recorded_mistake: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "last_critiques": list(self.last_critiques),
            "blocked": self.blocked,
            "recorded_mistake": self.recorded_mistake,
        }


@dataclass(frozen=True)
class ArtifactContext:
    skill_name: str
    artifact_kind: str
    ticket_id: str
    slug: str
    draft: str
    ground_truth: dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3

    @property
    def has_draft(self) -> bool:
        return bool(self.draft.strip())


@dataclass(frozen=True)
class CriticProfile:
    skill_name: str
    artifact_kind: str
    min_length: int = 120
    required_headings: tuple[str, ...] = ()
    extra_checks: tuple[Callable[[str, ArtifactContext], list[str]], ...] = ()

    def evaluate(
        self, draft: str, context: ArtifactContext, mistakes: list[dict[str, Any]]
    ) -> list[str]:
        critiques: list[str] = []
        text = draft.strip()
        if len(text) < self.min_length:
            critiques.append(
                f"Draft is too short to be actionable (minimum ~{self.min_length} characters)."
            )
        for heading in self.required_headings:
            if not re.search(rf"(?im)^#{{1,3}}\s+{re.escape(heading)}\s*$", text):
                critiques.append(f"Missing required section heading: '{heading}'.")
        if PLACEHOLDER_PATTERN.search(text):
            critiques.append(
                "Draft contains placeholder tokens (TODO/TBD/FIXME) — resolve before persisting."
            )
        for check in self.extra_checks:
            critiques.extend(check(text, context))
        for mistake in mistakes:
            flaw = str(mistake.get("flaw", "")).strip()
            if flaw and flaw.lower() in text.lower():
                critiques.append(
                    f"Repeats a recorded flaw from reflection history: {flaw}"
                )
        return critiques


@dataclass(frozen=True)
class ArtifactDecision:
    critiques: list[str]
    reflection: ReflectionState
    mode: str
    blocked: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "critiques": self.critiques,
            "reflection": self.reflection.to_dict(),
            "mode": self.mode,
            "blocked": self.blocked,
        }


def advance_reflection(
    state: ReflectionState, critiques: list[str], *, max_attempts: int = 3
) -> ReflectionState:
    attempt = state.attempt + 1
    normalized = tuple(critiques)
    identical = bool(normalized) and normalized == state.last_critiques
    return ReflectionState(
        attempt,
        normalized,
        bool(critiques) and (attempt >= max_attempts or identical),
        state.recorded_mistake,
    )


class ReflectionEngine:
    def __init__(self, profile: CriticProfile):
        self.profile = profile

    def evaluate_draft(
        self,
        context: ArtifactContext,
        *,
        state: ReflectionState | None = None,
        mistakes: list[dict[str, Any]] | None = None,
    ) -> ArtifactDecision:
        current = state or ReflectionState()
        if not context.has_draft:
            return ArtifactDecision([], current, "instructions", False)
        critiques = self.profile.evaluate(context.draft, context, mistakes or [])
        next_state = advance_reflection(
            current, critiques, max_attempts=context.max_attempts
        )
        blocked = next_state.blocked and bool(critiques)
        mode = (
            "completed"
            if not critiques
            else ("blocked_requires_review" if blocked else "instructions")
        )
        return ArtifactDecision(critiques, next_state, mode, blocked)

    def run_with_mistakes(
        self,
        context: ArtifactContext,
        *,
        state: ReflectionState | None = None,
        mistakes: list[dict[str, Any]] | None = None,
    ) -> ArtifactDecision:
        return self.evaluate_draft(context, state=state, mistakes=mistakes)
