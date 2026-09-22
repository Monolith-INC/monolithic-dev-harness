from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
FILENAME_RE = re.compile(r"^(\d+|tech-debt|bug|task|spike)-[a-z0-9-]+$")
LEGACY_FRONTMATTER_KEYS = ("azure_id", "parent_feature", "parent_epic")


@dataclass(frozen=True)
class ArtifactRecord:
    type: str
    title: str
    body: str
    story_points: float | None
    parent_id: str | None
    provider: str | None
    provider_id: str | None
    source: str
    filename: str | None
    frontmatter: dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    effort_hours: float | None = None
    """Estimated duration. None means unestimated -- which is honest, not a failure."""


def coerce_float(value: Any) -> float | None:
    """Best-effort numeric coercion for frontmatter values. Never raises."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fm_block = match.group(1)
    body = text[match.end() :]
    frontmatter: dict[str, Any] = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            frontmatter[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        elif value.isdigit():
            frontmatter[key] = int(value)
        else:
            try:
                frontmatter[key] = float(value)
            except ValueError:
                frontmatter[key] = value.strip("\"'")
    return frontmatter, body


def extract_title(body: str, frontmatter: dict[str, Any]) -> str:
    match = TITLE_RE.search(body)
    if match:
        return match.group(1).strip()
    for key in ("title", "System.Title"):
        if key in frontmatter:
            return str(frontmatter[key])
    return ""


def normalize_work_item_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    mapping = {
        "user story": "User Story",
        "story": "User Story",
        "feature": "Feature",
        "epic": "Epic",
        "task": "Task",
        "bug": "User Story",
        "tech debt": "User Story",
        "spike": "User Story",
    }
    return mapping.get(normalized, value.strip())


def _text_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _legacy_frontmatter_keys(frontmatter: dict[str, Any]) -> tuple[str, ...]:
    return tuple(key for key in LEGACY_FRONTMATTER_KEYS if key in frontmatter)


def ingest_from_text(text: str, *, filename: str | None = None) -> ArtifactRecord:
    frontmatter, body = parse_frontmatter(text)
    artifact_type = normalize_work_item_type(
        str(frontmatter.get("work_item_type") or frontmatter.get("type") or "User Story")
    )
    if artifact_type == "ticket":
        artifact_type = normalize_work_item_type(str(frontmatter.get("work_item_type", "User Story")))
    title = extract_title(body, frontmatter)
    story_points = frontmatter.get("story_points")
    if isinstance(story_points, str) and story_points.replace(".", "", 1).isdigit():
        story_points = float(story_points)
    return ArtifactRecord(
        type=artifact_type or "User Story",
        title=title,
        body=body,
        story_points=float(story_points) if isinstance(story_points, (int, float)) else None,
        parent_id=_text_or_none(frontmatter.get("parent_id")),
        provider=_text_or_none(frontmatter.get("provider")),
        provider_id=_text_or_none(frontmatter.get("provider_id")),
        source="file",
        filename=filename,
        frontmatter=frontmatter,
        raw=text,
        effort_hours=coerce_float(frontmatter.get("effort_hours")),
    )


def ingest_file(path: Path) -> ArtifactRecord:
    raw = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(raw)
    artifact_type = normalize_work_item_type(
        str(frontmatter.get("work_item_type") or frontmatter.get("type") or "")
    )
    if artifact_type == "ticket":
        artifact_type = normalize_work_item_type(str(frontmatter.get("work_item_type", "User Story")))
    title = extract_title(body, frontmatter)
    story_points = frontmatter.get("story_points")
    if isinstance(story_points, str) and story_points.replace(".", "", 1).isdigit():
        story_points = float(story_points)
    return ArtifactRecord(
        type=artifact_type or "User Story",
        title=title,
        body=body,
        story_points=float(story_points) if isinstance(story_points, (int, float)) else None,
        parent_id=_text_or_none(frontmatter.get("parent_id")),
        provider=_text_or_none(frontmatter.get("provider")),
        provider_id=_text_or_none(frontmatter.get("provider_id")),
        source="file",
        filename=path.stem,
        frontmatter=frontmatter,
        raw=raw,
        effort_hours=coerce_float(frontmatter.get("effort_hours")),
    )


def ingest_azure_record(
    *,
    provider: str = "azure-devops",
    work_item_type: str,
    title: str,
    description: str,
    story_points: float | None,
    parent_id: str | None,
    provider_id: str,
    effort_hours: float | None = None,
) -> ArtifactRecord:
    return ArtifactRecord(
        type=normalize_work_item_type(work_item_type) or work_item_type,
        title=title,
        body=description or "",
        story_points=story_points,
        parent_id=parent_id,
        provider=provider,
        provider_id=provider_id,
        source="azure",
        filename=None,
        frontmatter={},
        raw=description or "",
        effort_hours=effort_hours,
    )
