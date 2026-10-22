"""Whether a tracker item is refined: its text passes the agile-backlog-toolkit's `validate-artifact`.

Refinement is about an item's text (Constitution, Article 3): it is written in its type's template,
with the draft kept as Original Description. The toolkit's own validator decides, on the item as
the tracker holds it now. Section labels come in English or Brazilian Portuguese; an item passes
when it passes in either.
"""

from __future__ import annotations

import html
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.result import Ok, Result, err
from integrations.contracts import WorkItem, WorkItemKind
from integrations.payloads import as_float

_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

from orchestrator_core.artifact_validator import (  # noqa: E402
    critiques_from_results,
    outcome_from_results,
    validate_artifact,
)
from orchestrator_core.ingest import ArtifactRecord  # noqa: E402

_TYPES = {
    WorkItemKind.EPIC: "Epic",
    WorkItemKind.FEATURE: "Feature",
    WorkItemKind.USER_STORY: "User Story",
    WorkItemKind.BUG: "User Story",
    WorkItemKind.TASK: "Task",
}
# Where each tracker keeps a Story's points.
_POINTS = ("story_points", "Microsoft.VSTS.Scheduling.StoryPoints", "estimate")


def _points(data: Mapping[str, Any]) -> float | None:
    fields = data.get("fields")
    sources = (data, fields) if isinstance(fields, Mapping) else (data,)
    return next(
        (
            points
            for source in sources
            for name in _POINTS
            if (points := as_float(source.get(name))) is not None
        ),
        None,
    )


def _failures(item: WorkItem, language: str) -> list[str]:
    record = ArtifactRecord(
        type=_TYPES[item.kind],
        title=item.title,
        body=html.unescape(item.description),
        story_points=_points(item.provider_data),
        parent_id=item.parent_id or None,
        provider="tracker",
        provider_id=item.key,
        source="provider",
        filename=None,
        frontmatter={"language": language},
    )
    results = validate_artifact(record)
    return (
        []
        if outcome_from_results(results) == "PASS"
        else critiques_from_results(results)
    )


def check(item: WorkItem) -> Result[None]:
    """Ok when the item passes `validate-artifact`; otherwise what failed."""
    english, portuguese = _failures(item, "en"), _failures(item, "pt-br")
    if not english or not portuguese:
        return Ok(None)
    failed = min((english, portuguese), key=len)
    return err(
        "not_refined",
        f"{item.key} is not refined yet: it does not pass validate-artifact ("
        + "; ".join(failed)
        + "). Refine it first: enrich-work-item writes it in its type's template, keeping the "
        "draft as Original Description, and the user approves the new text.",
    )
