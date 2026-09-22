from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from .artifact_validator import CheckResult, outcome_from_results
from .ingest import ArtifactRecord


def format_terminal_report(record: ArtifactRecord, results: list[CheckResult]) -> str:
    lines: list[str] = []
    lines.append(f'Validating {record.type} — "{record.title}" [{record.source}]')
    lines.append("=" * 60)
    lines.append("")

    by_category: dict[str, list[CheckResult]] = defaultdict(list)
    for result in results:
        by_category[result.category].append(result)

    for category in ("STRUCTURAL", "HIERARCHY", "CONTENT", "DoR"):
        if category not in by_category:
            continue
        lines.append(category)
        for result in by_category[category]:
            detail = f"  —  {result.detail}" if result.detail else ""
            lines.append(f"  [{result.result}]  {result.name}{detail}")
        lines.append("")

    passed = sum(1 for r in results if r.result == "PASS")
    failed = sum(1 for r in results if r.result == "FAIL")
    warnings = sum(1 for r in results if r.result == "WARN")
    outcome = outcome_from_results(results)

    lines.append("-" * 60)
    lines.append(f"Summary: {passed} passed · {failed} failed · {warnings} warnings")
    lines.append(f"Outcome: {outcome}")
    return "\n".join(lines)


def artifact_slug(record: ArtifactRecord) -> str:
    if record.provider_id:
        return str(record.provider_id)
    if record.filename:
        return record.filename
    slug = record.title.lower().replace(" ", "-")
    return slug[:40] if slug else "unknown"


def persist_report(
    record: ArtifactRecord,
    terminal_output: str,
    *,
    state_dir: Path,
    skill: str | None = None,
) -> Path:
    """Write a validation report under the plugin's own state directory.

    Reports are plugin output, so they live in `.agile-backlog-toolkit/reports/` rather than in
    any user-owned location. Nothing is created outside that directory.
    """
    reports_dir = state_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    slug = artifact_slug(record)
    today = date.today().isoformat()
    prefix = "autofix" if skill == "auto-fix-artifact" else "validate"
    path = reports_dir / f"{today}-{prefix}-{slug}.md"
    outcome = "pass" if "Outcome: PASS" in terminal_output else "fail"
    frontmatter = [
        "---",
        f"date: {today}",
        "type: report",
        f"artifact: {slug}",
        f"artifact_type: {record.type}",
        f"source: {record.source}",
        f"outcome: {outcome}",
    ]
    if skill:
        frontmatter.append(f"skill: {skill}")
    frontmatter.append("---")
    body = "\n".join(frontmatter) + "\n\n```\n" + terminal_output + "\n```\n"
    path.write_text(body, encoding="utf-8")
    return path
