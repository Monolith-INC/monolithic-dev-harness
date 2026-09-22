from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from .ingest import FILENAME_RE, ArtifactRecord

# Section labels keyed by semantic name, one dict per supported `language:` frontmatter value.
# Order matters: dict insertion order is the required section order for that language.
SECTION_LABELS_BY_LANGUAGE: dict[str, dict[str, str]] = {
    "pt-br": {
        "what": "🎯 O quê",
        "why": "💡 Por quê",
        "expected_behavior": "📋 Comportamento esperado",
        "acceptance_criteria": "✅ Critérios de Aceite",
        "technical_notes": "🔧 Notas Técnicas",
        "complexity": "📊 Complexidade",
        "original_description": "📄 Descrição Original",
    },
    "en": {
        "what": "🎯 What",
        "why": "💡 Why",
        "expected_behavior": "📋 Expected Behavior",
        "acceptance_criteria": "✅ Acceptance Criteria",
        "technical_notes": "🔧 Technical Notes",
        "complexity": "📊 Complexity",
        "original_description": "📄 Original Description",
    },
}

STORY_SECTIONS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    lang: tuple(labels.values()) for lang, labels in SECTION_LABELS_BY_LANGUAGE.items()
}

COMPLEXITY_DRIVERS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "pt-br": ("Escopo", "Incerteza", "Integrações", "Dados", "QA", "Rollout"),
    "en": ("Scope", "Uncertainty", "Integrations", "Data", "QA", "Rollout"),
}

DEFAULT_LANGUAGE = "pt-br"

# Flat pt-BR defaults, kept for callers that still import the plain tuples directly
# (e.g. output_formats.py call sites that haven't opted into a `language` parameter).
STORY_SECTIONS = STORY_SECTIONS_BY_LANGUAGE[DEFAULT_LANGUAGE]
COMPLEXITY_DRIVERS = COMPLEXITY_DRIVERS_BY_LANGUAGE[DEFAULT_LANGUAGE]

MACHINE_PATH_RE = re.compile(r"(/home/|/Users/|C:\\|D:\\)")
META_PROSE_RE = re.compile(r"\b(TBD|to be defined|a definir)\b", re.I)


def resolve_language(frontmatter: dict[str, Any]) -> str:
    """Normalize a `language:` frontmatter value to a supported key; defaults to pt-BR.

    Accepts "en" or "pt-br"/"pt-BR" (case-insensitive); any other or missing value falls back
    to `DEFAULT_LANGUAGE` so pre-existing drafts without a `language:` key keep validating as
    pt-BR, the host team's original convention.
    """
    raw = str(frontmatter.get("language") or "").strip().lower()
    return raw if raw in SECTION_LABELS_BY_LANGUAGE else DEFAULT_LANGUAGE


def _has_meta_prose_outside_todo(body: str) -> re.Match | None:
    for line in body.splitlines():
        if "@TODO" in line:
            continue
        match = META_PROSE_RE.search(line)
        if match:
            return match
    return None


@dataclass(frozen=True)
class CheckResult:
    name: str
    result: str
    detail: str = ""
    category: str = ""


def _section_present(body: str, label: str) -> bool:
    pattern = rf"(?im)^#{{1,3}}\s+{re.escape(label)}\s*$"
    return bool(re.search(pattern, body))


def _section_content(body: str, label: str) -> str:
    pattern = rf"(?im)^#{{1,3}}\s+{re.escape(label)}\s*$\n(.*?)(?=^#{1,3}\s|\Z)"
    match = re.search(pattern, body, re.DOTALL)
    return match.group(1).strip() if match else ""


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _extract_h2_headings(body: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^#{2}\s+(.+)$", body, re.MULTILINE)]


BodyFormat = Literal["raw_generate", "enriched_story", "enriched_feature", "enriched_epic", "unknown"]


def _detect_body_format(body: str) -> BodyFormat:
    from .output_formats import ENRICH_EPIC_SECTIONS, ENRICH_FEATURE_SECTIONS

    h2 = _extract_h2_headings(body)
    if "Requisitos" in h2:
        return "raw_generate"
    all_story_sections = {
        section for sections in STORY_SECTIONS_BY_LANGUAGE.values() for section in sections
    }
    if any(section in h2 for section in all_story_sections):
        return "enriched_story"
    if any(section in h2 for section in ENRICH_FEATURE_SECTIONS):
        return "enriched_feature"
    if any(section in h2 for section in ENRICH_EPIC_SECTIONS):
        return "enriched_epic"
    return "unknown"


def _legacy_schema_message(frontmatter: dict[str, Any]) -> str | None:
    legacy = [key for key in ("azure_id", "parent_feature", "parent_epic") if key in frontmatter]
    if not legacy:
        return None
    return (
        "unsupported legacy frontmatter schema: "
        + ", ".join(legacy)
        + " — use provider, provider_id, and parent_id"
    )


def _effort_hours_check(record: ArtifactRecord, state_dir: Path | None = None) -> CheckResult:
    """Compare a declared duration against the band for its point value.

    Advisory only. An unestimated item SKIPs rather than FAILs: leaving the field empty is
    an honest state, and a made-up number would be worse than none. This check exists to
    catch a figure that contradicts its own story points, not to demand one.
    """
    from .estimation import EstimationConfig, estimate_hours, load_config

    # Honour the team's own bands when they have written any: warning a team against the
    # very table they replaced would make the check worse than useless.
    config = load_config(state_dir) if state_dir else EstimationConfig()

    hours = record.effort_hours
    if hours is None:
        return CheckResult("content-effort-hours-plausible", "SKIP", "no effort estimate recorded", "CONTENT")
    if hours <= 0:
        return CheckResult(
            "content-effort-hours-plausible", "WARN", f"effort_hours is {hours:g}; expected a positive number", "CONTENT"
        )

    expected = estimate_hours(record.story_points, config=config)
    if expected is None:
        return CheckResult(
            "content-effort-hours-plausible", "PASS", f"{hours:g}h (no story points to compare against)", "CONTENT"
        )
    if expected.low <= hours <= expected.high:
        return CheckResult(
            "content-effort-hours-plausible", "PASS", f"{hours:g}h within {expected.low:g}-{expected.high:g}h", "CONTENT"
        )
    return CheckResult(
        "content-effort-hours-plausible",
        "WARN",
        f"{hours:g}h sits outside the {expected.low:g}-{expected.high:g}h reference band "
        f"for {record.story_points:g} points; confirm the estimate or the points",
        "CONTENT",
    )


def _estimation_config_check(state_dir: Path | None = None) -> CheckResult:
    """Report malformed custom bands before validation falls back to seed defaults."""
    from .estimation import EstimationConfig, config_diagnostics, load_config

    config = load_config(state_dir) if state_dir else EstimationConfig()
    diagnostics = config_diagnostics(config)
    return CheckResult(
        "config-estimation-bands-valid",
        "WARN" if diagnostics else "PASS",
        "; ".join(diagnostics),
        "CONTENT",
    )


def _append_format_validation(
    results: list[CheckResult],
    *,
    name: str,
    fmt_result,
) -> None:
    if fmt_result.ok:
        results.append(CheckResult(name, "PASS", "", "STRUCTURAL"))
        return
    for error in fmt_result.errors:
        results.append(CheckResult(name, "FAIL", error, "STRUCTURAL"))


def validate_artifact(
    record: ArtifactRecord,
    *,
    hierarchy_parent_is_feature: bool | None = None,
    state_dir: Path | None = None,
) -> list[CheckResult]:
    """Rule-based validation mirroring validation-checks.md."""
    results: list[CheckResult] = []
    artifact_type = record.type
    language = resolve_language(record.frontmatter)
    section_labels = SECTION_LABELS_BY_LANGUAGE[language]
    complexity_drivers = COMPLEXITY_DRIVERS_BY_LANGUAGE[language]
    story_sections = STORY_SECTIONS_BY_LANGUAGE[language]

    if record.source == "file":
        legacy_schema = _legacy_schema_message(record.frontmatter)
        if legacy_schema:
            results.append(
                CheckResult(
                    "frontmatter-legacy-schema",
                    "FAIL",
                    legacy_schema,
                    "STRUCTURAL",
                )
            )
        results.append(
            CheckResult(
                "frontmatter-type-present",
                "PASS" if record.frontmatter.get("type") else "FAIL",
                "" if record.frontmatter.get("type") else "`type:` key missing from frontmatter",
                "STRUCTURAL",
            )
        )
        results.append(
            CheckResult(
                "frontmatter-status-absent",
                "FAIL" if "status" in record.frontmatter else "PASS",
                "`status:` found in frontmatter" if "status" in record.frontmatter else "",
                "STRUCTURAL",
            )
        )
        if record.filename:
            ok = bool(FILENAME_RE.match(record.filename))
            results.append(
                CheckResult(
                    "filename-regex",
                    "PASS" if ok else "FAIL",
                    "" if ok else f"filename `{record.filename}` does not match required pattern",
                    "STRUCTURAL",
                )
            )
    else:
        for name in ("frontmatter-type-present", "frontmatter-status-absent", "filename-regex"):
            results.append(
                CheckResult(name, "SKIP", "source is Azure, not a local file", "STRUCTURAL")
            )

    body_format = _detect_body_format(record.body)

    if body_format == "raw_generate":
        from .output_formats import validate_generate_work_item_body

        _append_format_validation(
            results,
            name="body-raw-generate-format",
            fmt_result=validate_generate_work_item_body(record.body),
        )
    elif artifact_type == "User Story":
        if body_format == "enriched_story":
            from .output_formats import (
                validate_enrich_user_story_body,
                validate_ticket_structure_body,
            )

            fmt_result = (
                validate_ticket_structure_body(record.body, language=language)
                if all(_section_present(record.body, section) for section in story_sections)
                else validate_enrich_user_story_body(record.body)
            )
            _append_format_validation(results, name="body-enriched-story-format", fmt_result=fmt_result)
        else:
            missing_sections: list[str] = []
            for section in story_sections:
                if not _section_present(record.body, section):
                    missing_sections.append(section)
                    results.append(
                        CheckResult(
                            f"body-section-missing: {section}",
                            "FAIL",
                            f"section `{section}` absent",
                            "STRUCTURAL",
                        )
                    )
            if not missing_sections:
                results.append(
                    CheckResult(
                        "body-sections",
                        "PASS",
                        f"all {len(story_sections)} required sections present ({language})",
                        "STRUCTURAL",
                    )
                )
    elif artifact_type in {"Feature", "Task"}:
        if body_format == "enriched_feature":
            from .output_formats import validate_enrich_feature_body

            _append_format_validation(
                results,
                name="body-enriched-feature-format",
                fmt_result=validate_enrich_feature_body(record.body),
            )
        else:
            title_ok = bool(record.title.strip())
            desc_ok = bool(record.body.strip())
            results.append(
                CheckResult(
                    "body-title-present",
                    "PASS" if title_ok else "FAIL",
                    "" if title_ok else "title is empty",
                    "STRUCTURAL",
                )
            )
            results.append(
                CheckResult(
                    "body-description-present",
                    "PASS" if desc_ok else "FAIL",
                    "" if desc_ok else "description is empty",
                    "STRUCTURAL",
                )
            )
    elif artifact_type == "Epic":
        if body_format == "enriched_epic":
            from .output_formats import validate_enrich_epic_body

            _append_format_validation(
                results,
                name="body-enriched-epic-format",
                fmt_result=validate_enrich_epic_body(record.body),
            )
        else:
            title_ok = bool(record.title.strip())
            desc_ok = bool(record.body.strip())
            results.append(
                CheckResult(
                    "body-title-present",
                    "PASS" if title_ok else "FAIL",
                    "" if title_ok else "title is empty",
                    "STRUCTURAL",
                )
            )
            results.append(
                CheckResult(
                    "body-description-present",
                    "PASS" if desc_ok else "FAIL",
                    "" if desc_ok else "description is empty",
                    "STRUCTURAL",
                )
            )

    if record.source == "file" and not record.provider_id:
        results.append(
            CheckResult(
                "hierarchy-skipped-no-provider-id",
                "WARN",
                "no provider_id in frontmatter, hierarchy checks skipped",
                "HIERARCHY",
            )
        )
        hierarchy_story_ok = None
    else:
        if artifact_type == "User Story":
            if hierarchy_parent_is_feature is True:
                results.append(
                    CheckResult(
                        "hierarchy-story-parent-is-feature",
                        "PASS",
                        "",
                        "HIERARCHY",
                    )
                )
                hierarchy_story_ok = True
            elif hierarchy_parent_is_feature is False:
                results.append(
                    CheckResult(
                        "hierarchy-story-parent-is-feature",
                        "FAIL",
                        "parent is not a Feature or is missing",
                        "HIERARCHY",
                    )
                )
                hierarchy_story_ok = False
            else:
                results.append(
                    CheckResult(
                        "hierarchy-story-parent-is-feature",
                        "SKIP",
                        "hierarchy not verified (no Azure MCP data)",
                        "HIERARCHY",
                    )
                )
                hierarchy_story_ok = None
        else:
            hierarchy_story_ok = None

    if artifact_type == "User Story" and body_format != "raw_generate":
        complexidade = _section_content(record.body, section_labels["complexity"])
        drivers_ok = complexidade and all(d in complexidade for d in complexity_drivers)
        results.append(
            CheckResult(
                "content-complexidade-breakdown",
                "PASS" if drivers_ok else "FAIL",
                "" if drivers_ok else f"missing one or more driver keywords in {section_labels['complexity']} section",
                "CONTENT",
            )
        )
        sp = record.story_points
        sp_ok = sp is not None and sp > 0
        results.append(
            CheckResult(
                "content-story-points-set",
                "PASS" if sp_ok else "FAIL",
                f"{int(sp)} points" if sp_ok else "story_points not set or zero",
                "CONTENT",
            )
        )
        desc_orig = _section_content(record.body, section_labels["original_description"])
        results.append(
            CheckResult(
                "content-descricao-original-present",
                "PASS" if desc_orig else "FAIL",
                "" if desc_orig else f"{section_labels['original_description']} section is empty",
                "CONTENT",
            )
        )

    path_match = MACHINE_PATH_RE.search(record.body)
    results.append(
        CheckResult(
            "content-no-machine-paths",
            "WARN" if path_match else "PASS",
            f"found: {path_match.group(0)}" if path_match else "",
            "CONTENT",
        )
    )
    meta_match = _has_meta_prose_outside_todo(record.body)
    results.append(
        CheckResult(
            "content-no-meta-prose",
            "WARN" if meta_match else "PASS",
            f"found: {meta_match.group(0)}" if meta_match else "",
            "CONTENT",
        )
    )
    results.append(_estimation_config_check(state_dir))
    results.append(_effort_hours_check(record, state_dir))

    title_words = _word_count(record.title)
    results.append(
        CheckResult(
            "dor-title-clear",
            "PASS" if title_words > 5 else "FAIL",
            f"{title_words} words" if title_words <= 5 else "",
            "DoR",
        )
    )
    results.append(
        CheckResult(
            "dor-description-present",
            "PASS" if record.body.strip() else "FAIL",
            "" if record.body.strip() else "body/description is empty",
            "DoR",
        )
    )
    if artifact_type in {"User Story", "Task"}:
        if body_format == "raw_generate":
            results.append(
                CheckResult(
                    "dor-story-points-set",
                    "SKIP" if artifact_type == "User Story" else "PASS",
                    "raw generate-work-item draft — run enrich-work-item before sizing"
                    if artifact_type == "User Story"
                    else "task artifacts do not carry story points",
                    "DoR",
                )
            )
        else:
            sp = record.story_points
            sp_ok = artifact_type == "Task" or (sp is not None and sp > 0)
            results.append(
                CheckResult(
                    "dor-story-points-set",
                    "PASS" if sp_ok else "FAIL",
                    "" if sp_ok else "story points not set",
                    "DoR",
                )
            )
        if hierarchy_story_ok is True:
            dor_link = "PASS"
            dor_detail = ""
        elif hierarchy_story_ok is False:
            dor_link = "FAIL"
            dor_detail = "hierarchy-story-parent-is-feature failed"
        else:
            dor_link = "SKIP"
            dor_detail = "hierarchy check skipped"
        results.append(
            CheckResult(
                "dor-linked-to-feature",
                dor_link,
                dor_detail,
                "DoR",
            )
        )

    return results


def critiques_from_results(results: Iterable[CheckResult]) -> list[str]:
    return [
        f"{r.name}: {r.detail}".rstrip(": ")
        for r in results
        if r.result in ("FAIL", "WARN") and (r.detail or r.name)
    ]


def outcome_from_results(results: Iterable[CheckResult]) -> str:
    return "FAIL" if any(r.result == "FAIL" for r in results) else "PASS"
