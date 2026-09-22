from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SPEC_KINDS = (
    "rfc",
    "adr",
    "design-doc",
    "tech-spec",
    "srs",
    "implementation-plan",
    "bugfix-spec",
    "api-contract",
)
DEFAULT_KINDS_BY_SIGNAL = {
    "bugfix": ("bugfix-spec", "adr"),
    "feature": ("design-doc", "tech-spec"),
    "task": ("implementation-plan", "tech-spec"),
    "refactor": ("adr", "tech-spec"),
    "default": ("tech-spec", "implementation-plan"),
}


@dataclass(frozen=True)
class SpecPlan:
    ticket_id: str
    slug: str
    existing_artifacts: tuple[str, ...]
    required_kinds: tuple[str, ...]
    missing_kinds: tuple[str, ...]
    generation_required: bool
    source_hints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "slug": self.slug,
            "existing_artifacts": list(self.existing_artifacts),
            "required_kinds": list(self.required_kinds),
            "missing_kinds": list(self.missing_kinds),
            "generation_required": self.generation_required,
            "source_hints": dict(self.source_hints),
        }


def slug_ticket_id(ticket_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ticket_id.strip()).strip("-").lower()
    return slug or "ticket"


def infer_ticket_signal(ticket_id: str, source_text: str = "") -> str:
    combined = f"{ticket_id}\n{source_text}".lower()
    if re.search(r"\bbug(fix)?\b", combined) or "type: bug" in combined:
        return "bugfix"
    if re.search(r"\brefactor\b", combined):
        return "refactor"
    if re.search(r"\bfeature\b", combined):
        return "feature"
    if re.search(r"\btask\b", combined):
        return "task"
    return "default"


def kinds_for_signal(signal: str) -> tuple[str, ...]:
    return DEFAULT_KINDS_BY_SIGNAL.get(signal, DEFAULT_KINDS_BY_SIGNAL["default"])


def missing_spec_kinds(
    existing_artifacts: list[str] | tuple[str, ...], desired_kinds: tuple[str, ...]
) -> list[str]:
    existing = {str(name).removesuffix(".md").lower() for name in existing_artifacts}
    return [kind for kind in desired_kinds if kind not in existing]


def _extract_source_hints(source_text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    for label, pattern in (
        ("requirements", r"(?im)^(?:##\s*)?requirements?\s*[:\n](.+?)(?:\n##|\Z)"),
        ("description", r"(?im)^(?:##\s*)?description\s*[:\n](.+?)(?:\n##|\Z)"),
        (
            "implementation_plan",
            r"(?im)^(?:##\s*)?implementation\s+plan\s*[:\n](.+?)(?:\n##|\Z)",
        ),
    ):
        match = re.search(pattern, source_text, re.DOTALL)
        if match:
            hints[label] = match.group(1).strip()[:2000]
    if not hints and source_text.strip():
        hints["description"] = source_text.strip()[:2000]
    return hints


def plan_spec_generation(
    ticket_id: str,
    *,
    source_text: str = "",
    existing_artifacts: list[str] | tuple[str, ...] = (),
    required_kinds: list[str] | tuple[str, ...] | None = None,
    kind: str | None = None,
) -> SpecPlan:
    desired = tuple(
        required_kinds
        or (
            (kind,)
            if kind
            else kinds_for_signal(infer_ticket_signal(ticket_id, source_text))
        )
    )
    existing = tuple(str(item) for item in existing_artifacts)
    missing = missing_spec_kinds(existing, desired)
    return SpecPlan(
        ticket_id,
        slug_ticket_id(ticket_id),
        existing,
        desired,
        tuple(missing),
        bool(missing),
        _extract_source_hints(source_text),
    )


def template_path(skills_dir: Path, kind: str) -> Path:
    return skills_dir / "write-spec" / "references" / "templates" / f"{kind}.md"


def load_template(skills_dir: Path, kind: str) -> str:
    path = template_path(skills_dir, kind)
    if not path.is_file():
        raise FileNotFoundError(f"Missing spec template for kind '{kind}': {path}")
    return path.read_text(encoding="utf-8")
