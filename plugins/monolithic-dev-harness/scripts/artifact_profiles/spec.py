from __future__ import annotations

import re

from artifact_reflection import ArtifactContext, CriticProfile

SPEC_REQUIRED_HEADINGS: dict[str, tuple[str, ...]] = {
    "rfc": ("Summary", "Motivation", "Proposal", "Alternatives", "Open Questions"),
    "adr": ("Status", "Context", "Decision", "Consequences"),
    "design-doc": ("Context", "Goals", "Non-Goals", "Proposed Design"),
    "tech-spec": ("Overview", "Data Model", "API", "Implementation Plan"),
    "srs": ("Introduction", "Functional Requirements", "Non-Functional Requirements"),
    "implementation-plan": ("Scope", "Milestones", "Validation"),
    "bugfix-spec": ("Problem Statement", "Root Cause", "Fix Strategy", "Verification"),
    "api-contract": ("Endpoints", "Schemas", "Error Handling"),
}


def _spec_normative_check(text: str, context: ArtifactContext) -> list[str]:
    kind = context.artifact_kind
    if kind in {"tech-spec", "srs", "api-contract"} and not re.search(
        r"(?im)\b(MUST|SHOULD|MAY)\b", text
    ):
        return [
            "Normative requirements should use RFC 2119 keywords (MUST/SHOULD/MAY)."
        ]
    return []


def _spec_non_goals_check(text: str, context: ArtifactContext) -> list[str]:
    if context.artifact_kind == "design-doc" and not re.search(r"(?im)non-goal", text):
        return ["Design doc should explicitly list Non-Goals to bound scope."]
    return []


def _spec_rollback_check(text: str, context: ArtifactContext) -> list[str]:
    if context.artifact_kind in {
        "tech-spec",
        "implementation-plan",
        "bugfix-spec",
    } and not re.search(r"(?im)(rollback|revert|mitigation)", text):
        return ["Missing rollback or mitigation plan for failed implementation."]
    return []


def spec_profile(spec_kind: str) -> CriticProfile:
    return CriticProfile(
        skill_name="write-spec",
        artifact_kind=spec_kind,
        required_headings=SPEC_REQUIRED_HEADINGS.get(spec_kind, ()),
        extra_checks=(
            _spec_normative_check,
            _spec_non_goals_check,
            _spec_rollback_check,
        ),
    )
