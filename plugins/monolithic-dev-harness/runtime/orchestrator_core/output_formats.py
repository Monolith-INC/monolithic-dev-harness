"""Structural validators for agile-backlog-toolkit skill output contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .artifact_validator import (
    COMPLEXITY_DRIVERS,
    COMPLEXITY_DRIVERS_BY_LANGUAGE,
    DEFAULT_LANGUAGE,
    SECTION_LABELS_BY_LANGUAGE,
    STORY_SECTIONS_BY_LANGUAGE,
)

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
BOLD_SECTION_RE = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)
SPEC_WIKILINK_RE = re.compile(r"\[\[Specs/[^\]]+\]\]")
CHECKBOX_RE = re.compile(r"^- \[[ xX]\] ", re.MULTILINE)

GENERATE_WORK_ITEM_SECTIONS = ("Requisitos", "Critérios de Aceite")

ENRICH_EPIC_SECTIONS = (
    "🎯 Visão Estratégica",
    "📊 Problema de Negócio",
    "🎯 Objetivos Estratégicos",
    "📈 Métricas de Sucesso (KPIs/OKRs)",
    "📦 Escopo Estratégico",
    "🔧 Áreas/Projetos Envolvidos",
    "🔗 Dependências e Riscos Estratégicos",
    "📄 Descrição Original",
)

ENRICH_FEATURE_SECTIONS = (
    "🎯 Objetivo",
    "📦 Escopo",
    "✅ Critérios de Sucesso",
    "🔧 Áreas/Módulos Envolvidos",
    "📄 Descrição Original",
)

ENRICH_USER_STORY_REQUIRED = (
    "🎯 O quê",
    "💡 Por quê",
    "✅ Critérios de Aceite",
    "📊 Complexidade",
    "📄 Descrição Original",
)

ENRICH_USER_STORY_OPTIONAL = (
    "📋 Comportamento esperado",
    "🔧 Notas Técnicas",
    "🔄 Como Reproduzir",
    "📎 Anexos / Referências",
)

FORBIDDEN_GENERATE_EMOJI_SECTIONS = frozenset(
    ENRICH_EPIC_SECTIONS
    + ENRICH_FEATURE_SECTIONS
    + ENRICH_USER_STORY_REQUIRED
    + ENRICH_USER_STORY_OPTIONAL
)

SPIKE_BOLD_SECTIONS = (
    "🎯 O quê",
    "💡 Por quê",
    "📋 Comportamento esperado",
    "✅ Critérios de Aceite",
    "📊 Complexidade",
    "📄 Descrição Original",
)

VALIDATION_REPORT_CATEGORIES = ("STRUCTURAL", "HIERARCHY", "CONTENT", "DoR")


@dataclass
class FormatValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


def _extract_h2_headings(body: str) -> list[str]:
    return [label.strip() for level, label in _extract_headings(body) if level == 2]


def _extract_headings(body: str) -> list[tuple[int, str]]:
    return [(len(m.group(1)), m.group(2).strip()) for m in HEADING_RE.finditer(body)]


def _extract_bold_sections(body: str) -> list[str]:
    return [m.group(1).strip() for m in BOLD_SECTION_RE.finditer(body)]


def _sections_in_order(body: str, required: tuple[str, ...]) -> FormatValidationResult:
    headings = _extract_h2_headings(body)
    errors: list[str] = []
    missing = [s for s in required if s not in headings]
    if missing:
        errors.append(f"missing sections: {', '.join(missing)}")

    indices = [headings.index(s) for s in required if s in headings]
    if indices and indices != sorted(indices):
        errors.append(f"sections out of order; expected {list(required)}")

    return FormatValidationResult(ok=not errors, errors=errors)


def _section_content(body: str, label: str) -> str:
    pattern = rf"(?im)^#{{2}}\s+{re.escape(label)}\s*$\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, body, re.DOTALL)
    return match.group(1).strip() if match else ""


def validate_generate_work_item_body(body: str) -> FormatValidationResult:
    """Uniform raw ticket body for epic, feature, and user-story."""
    errors: list[str] = []
    headings = _extract_headings(body)

    h1 = [label for level, label in headings if level == 1]
    if len(h1) != 1:
        errors.append("exactly one H1 title heading required")
    elif not h1[0].strip():
        errors.append("H1 title must be non-empty")

    if not SPEC_WIKILINK_RE.search(body):
        errors.append("missing [[Specs/<basename>]] wikilink")

    h2_labels = _extract_h2_headings(body)
    for section in GENERATE_WORK_ITEM_SECTIONS:
        if section not in h2_labels:
            errors.append(f"missing section: ## {section}")

    order_result = _sections_in_order(body, GENERATE_WORK_ITEM_SECTIONS)
    errors.extend(order_result.errors)

    for emoji_section in FORBIDDEN_GENERATE_EMOJI_SECTIONS:
        if emoji_section in h2_labels:
            errors.append(f"forbidden enricher section present: ## {emoji_section}")

    ac_body = _section_content(body, "Critérios de Aceite")
    if ac_body and not CHECKBOX_RE.search(ac_body):
        errors.append("Critérios de Aceite must use - [ ] checkbox items")

    return FormatValidationResult(ok=not errors, errors=errors)


def validate_enrich_epic_body(body: str) -> FormatValidationResult:
    return _sections_in_order(body, ENRICH_EPIC_SECTIONS)


def validate_enrich_feature_body(body: str) -> FormatValidationResult:
    result = _sections_in_order(body, ENRICH_FEATURE_SECTIONS)
    if result.ok:
        success = _section_content(body, "✅ Critérios de Sucesso")
        if success and not CHECKBOX_RE.search(success):
            return FormatValidationResult(
                ok=False,
                errors=["Critérios de Sucesso must use - [ ] checkbox items"],
            )
    return result


def validate_enrich_user_story_body(body: str) -> FormatValidationResult:
    result = _sections_in_order(body, ENRICH_USER_STORY_REQUIRED)
    if not result.ok:
        return result

    errors: list[str] = []
    ac_body = _section_content(body, "✅ Critérios de Aceite")
    if ac_body and not CHECKBOX_RE.search(ac_body):
        errors.append("Critérios de Aceite must use - [ ] checkbox items")

    complexidade = _section_content(body, "📊 Complexidade")
    if complexidade and not all(driver in complexidade for driver in COMPLEXITY_DRIVERS):
        errors.append("Complexidade must mention all six drivers")

    desc_orig = _section_content(body, "📄 Descrição Original")
    if not desc_orig:
        errors.append("Descrição Original must be non-empty")

    return FormatValidationResult(ok=not errors, errors=errors)


def validate_ticket_structure_body(
    body: str, *, language: str = DEFAULT_LANGUAGE
) -> FormatValidationResult:
    """Seven-section enriched user story (decompose-backlog, split-story).

    `language` selects which label set (`en` or `pt-br`) the section headings and complexity
    drivers must match; defaults to pt-BR, the host team's original convention.
    """
    language = language if language in SECTION_LABELS_BY_LANGUAGE else DEFAULT_LANGUAGE
    labels = SECTION_LABELS_BY_LANGUAGE[language]
    sections = STORY_SECTIONS_BY_LANGUAGE[language]
    drivers = COMPLEXITY_DRIVERS_BY_LANGUAGE[language]

    result = _sections_in_order(body, sections)
    if not result.ok:
        return result

    errors: list[str] = []
    ac_body = _section_content(body, labels["acceptance_criteria"])
    if ac_body and not CHECKBOX_RE.search(ac_body):
        errors.append(f"{labels['acceptance_criteria']} must use - [ ] checkbox items")

    complexidade = _section_content(body, labels["complexity"])
    if complexidade and not all(driver in complexidade for driver in drivers):
        errors.append(f"{labels['complexity']} must mention all six drivers")

    desc_orig = _section_content(body, labels["original_description"])
    if not desc_orig:
        errors.append(f"{labels['original_description']} must be non-empty")

    return FormatValidationResult(ok=not errors, errors=errors)


def validate_split_story_spike_body(body: str) -> FormatValidationResult:
    """Spike stub uses bold labels instead of ## headings."""
    sections = _extract_bold_sections(body)
    errors: list[str] = []
    missing = [s for s in SPIKE_BOLD_SECTIONS if s not in sections]
    if missing:
        errors.append(f"missing bold sections: {', '.join(missing)}")

    indices = [sections.index(s) for s in SPIKE_BOLD_SECTIONS if s in sections]
    if indices and indices != sorted(indices):
        errors.append(f"spike sections out of order; expected {list(SPIKE_BOLD_SECTIONS)}")

    ac_match = re.search(
        r"(?is)\*\*✅ Critérios de Aceite\*\*\s*\n(.*?)(?=\n\*\*|\Z)",
        body,
    )
    if ac_match and not CHECKBOX_RE.search(ac_match.group(1)):
        errors.append("Spike Critérios de Aceite must use - [ ] checkbox items")

    return FormatValidationResult(ok=not errors, errors=errors)


def validate_validation_report_body(body: str) -> FormatValidationResult:
    """Terminal validation report shape from report-format.md."""
    errors: list[str] = []
    lines = body.strip().splitlines()

    if not lines or not lines[0].startswith("Validating "):
        errors.append("report must start with 'Validating <type> — \"<title>\" [<source>]'")

    if len(lines) < 2 or lines[1] != "=" * 60:
        errors.append("second line must be 60 '=' characters")

    footer_sep_idx = next((i for i, line in enumerate(lines) if line == "-" * 60), None)
    if footer_sep_idx is None:
        errors.append("missing 60 '-' separator before summary")

    body_text = "\n".join(lines)
    for category in VALIDATION_REPORT_CATEGORIES:
        if category not in body_text:
            errors.append(f"missing category block: {category}")

    if not re.search(r"^Summary: \d+ passed · \d+ failed · \d+ warnings\s*$", body, re.M):
        errors.append("missing Summary line")

    if not re.search(r"^Outcome: (PASS|FAIL)\s*$", body, re.M):
        errors.append("missing Outcome: PASS or Outcome: FAIL")

    check_lines = [line for line in lines if re.match(r"^\s+\[(PASS|FAIL|WARN|SKIP)\]", line)]
    if not check_lines:
        errors.append("report must include at least one check result line")

    return FormatValidationResult(ok=not errors, errors=errors)
