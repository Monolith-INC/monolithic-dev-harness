from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESOLUTION_REPORT = "resolution-report.md"


@dataclass(frozen=True)
class ResolutionPlan:
    ticket_id: str
    spec_artifacts: tuple[str, ...]
    resolution_required: bool
    source_hints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "spec_artifacts": list(self.spec_artifacts),
            "resolution_required": self.resolution_required,
            "source_hints": dict(self.source_hints),
        }

    def ground_truth(self) -> dict[str, Any]:
        return {
            "spec_artifacts": list(self.spec_artifacts),
            "requirements": self.source_hints.get("requirements", ""),
            "implementation_summary": self.source_hints.get(
                "implementation_summary", ""
            ),
            "description": self.source_hints.get("description", ""),
        }


def _extract_resolution_hints(source_text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    for label, pattern in (
        ("requirements", r"(?im)^(?:##\s*)?requirements?\s*[:\n](.+?)(?:\n##|\Z)"),
        ("description", r"(?im)^(?:##\s*)?description\s*[:\n](.+?)(?:\n##|\Z)"),
        (
            "implementation_summary",
            r"(?im)^(?:##\s*)?implementation\s+(?:summary|walkthrough)\s*[:\n](.+?)(?:\n##|\Z)",
        ),
        ("verification", r"(?im)^(?:##\s*)?verification\s*[:\n](.+?)(?:\n##|\Z)"),
    ):
        match = re.search(pattern, source_text, re.DOTALL)
        if match:
            hints[label] = match.group(1).strip()[:4000]
    return hints


def plan_resolution(
    ticket_id: str,
    *,
    source_text: str = "",
    artifacts: list[str] | tuple[str, ...] = (),
    resolution_exists: bool = False,
) -> ResolutionPlan:
    specs = tuple(
        str(item)
        for item in artifacts
        if str(item) not in {RESOLUTION_REPORT, "resolution_report"}
    )
    return ResolutionPlan(
        ticket_id,
        specs,
        not resolution_exists or not bool(specs),
        _extract_resolution_hints(source_text),
    )


def template_path(skills_dir: Path) -> Path:
    return (
        skills_dir / "resolve-ticket" / "references" / "templates" / RESOLUTION_REPORT
    )


def load_resolution_template(skills_dir: Path) -> str:
    path = template_path(skills_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Missing resolution template: {path}")
    return path.read_text(encoding="utf-8")
