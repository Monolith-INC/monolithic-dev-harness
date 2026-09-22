from __future__ import annotations

import re

from artifact_reflection import ArtifactContext, CriticProfile

RESOLUTION_HEADINGS = (
    "Problem Recap",
    "Spec Coverage",
    "Implementation Summary",
    "Verification",
    "Residual Risks",
)


def _require_ground_truth_specs(text: str, context: ArtifactContext) -> list[str]:
    critiques: list[str] = []
    specs = context.ground_truth.get("spec_artifacts", [])
    if not specs:
        critiques.append(
            "No spec files found for this ticket — write-spec must run before resolve-ticket."
        )
        return critiques

    spec_names = [name.removesuffix(".md") for name in specs]
    missing_refs = [
        name
        for name in spec_names
        if name.replace("-", " ") not in text.lower() and name not in text.lower()
    ]
    if missing_refs:
        critiques.append(
            "Resolution report must reference each spec file: "
            + ", ".join(missing_refs)
            + "."
        )
    return critiques


def _require_implementation_evidence(text: str, context: ArtifactContext) -> list[str]:
    critiques: list[str] = []
    summary = str(context.ground_truth.get("implementation_summary", "")).strip()
    if summary and summary.lower() not in text.lower() and len(summary) > 40:
        critiques.append(
            "Implementation summary supplied by the work item is not reflected in the resolution report."
        )

    if not re.search(r"(?im)(commit|pr|pull request|file|module|test)", text):
        critiques.append(
            "Implementation Summary must cite concrete evidence (files, commits, PR, or tests)."
        )
    return critiques


def _require_verification(text: str, context: ArtifactContext) -> list[str]:
    if not re.search(r"(?im)(test|validation|verified|passing|qa)", text):
        return ["Verification section must document how the work was validated."]
    return []


def _map_requirements_to_specs(text: str, context: ArtifactContext) -> list[str]:
    requirements = str(context.ground_truth.get("requirements", "")).strip()
    if not requirements:
        return []
    if not re.search(
        r"(?im)(requirement|acceptance|satisfied|deferred|out of scope)", text
    ):
        return ["Spec Coverage must map requirements to satisfied/deferred outcomes."]
    return []


def resolution_profile() -> CriticProfile:
    return CriticProfile(
        skill_name="resolve-ticket",
        artifact_kind="resolution-report",
        required_headings=RESOLUTION_HEADINGS,
        extra_checks=(
            _require_ground_truth_specs,
            _require_implementation_evidence,
            _require_verification,
            _map_requirements_to_specs,
        ),
    )
