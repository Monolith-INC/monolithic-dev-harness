from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..capacity.model import (
    ActivityCapacity,
    DateRange,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
    parse_date,
)
from ..ingest import parse_frontmatter
from .base import ProviderResult, WriteOp

# Conventional sub-paths looked for *underneath the path the user supplied*. The plugin
# creates none of them and requires none of them; they are only where it looks first.
TICKET_DIRS = ("Tickets/Ready", "Tickets/InProgress", "Tickets/Done", "Tickets", ".")
CAPACITY_FILENAME = "capacity-{iteration}.json"


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _first_present(entry: dict, *names: str) -> float | None:
    """First key actually present. Not an `or` chain: a legitimate 0 is falsy."""
    for name in names:
        value = _as_float(entry.get(name))
        if value is not None:
            return value
    return None


def _ranges_from(raw: Any) -> tuple[DateRange, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[DateRange] = []
    for entry in raw:
        if isinstance(entry, dict):
            start = parse_date(entry.get("start"))
            end = parse_date(entry.get("end")) or start
        elif isinstance(entry, str):
            start = parse_date(entry)
            end = start
        else:
            continue
        if start and end:
            out.append(DateRange(start, end))
    return tuple(out)


class FilesystemProvider:
    """Reads estimation and capacity data from a directory the user nominated.

    The plugin has no opinion about what that directory is or what else lives there. It
    reads markdown frontmatter from it, creates nothing, and refuses with an explanation
    rather than guessing when no path has been configured.
    """

    name = "filesystem"

    NO_PATH = (
        "No artifacts path configured. Ask the user where local artifacts should be written, "
        "then save it with: bin/agile-backlog-toolkit config --set artifacts_path=<path>"
    )

    def __init__(self, artifacts_dir: Path | None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    @property
    def configured(self) -> bool:
        return self.artifacts_dir is not None

    # -- reads -------------------------------------------------------------

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        if not self.configured:
            return ProviderResult.failure(self.NO_PATH)
        path = self.artifacts_dir / CAPACITY_FILENAME.format(iteration=iteration_ref)
        if not path.is_file():
            return ProviderResult.success(
                IterationCapacity(iteration_ref=iteration_ref),
                warnings=(f"no capacity file at {path}; iteration has no team or dates",),
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            # A file that exists but cannot be read is a fixable misconfiguration, not the
            # normal absence above. Saying "no such file" would send someone the wrong way.
            return ProviderResult.failure(f"capacity file unreadable: {path}: {exc}")
        if not isinstance(data, dict):
            return ProviderResult.failure(f"capacity file is not an object: {path}")

        members: list[MemberCapacity] = []
        for entry in data.get("members", []) if isinstance(data.get("members"), list) else []:
            if not isinstance(entry, dict):
                continue
            activities = tuple(
                ActivityCapacity(
                    name=str(a.get("name", "")),
                    capacity_per_day=_first_present(a, "capacityPerDay", "capacity_per_day") or 0.0,
                )
                for a in entry.get("activities", [])
                if isinstance(a, dict)
            )
            members.append(
                MemberCapacity(
                    member_id=str(entry.get("id") or entry.get("name") or ""),
                    display_name=str(entry.get("name") or entry.get("id") or ""),
                    activities=activities,
                    days_off=_ranges_from(entry.get("daysOff") or entry.get("days_off")),
                )
            )

        return ProviderResult.success(
            IterationCapacity(
                iteration_ref=iteration_ref,
                start_date=parse_date(data.get("startDate") or data.get("start_date")),
                finish_date=parse_date(data.get("finishDate") or data.get("finish_date")),
                members=tuple(members),
                team_days_off=_ranges_from(data.get("teamDaysOff") or data.get("team_days_off")),
            )
        )

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        """Collect ticket drafts whose frontmatter names this iteration.

        A draft with no `iteration` key is included when `iteration_ref` is empty, so the
        common case of a directory with no sprint metadata still produces a useful total.
        """
        if not self.configured:
            return ProviderResult.failure(self.NO_PATH)

        items: list[EstimableItem] = []
        warnings: list[str] = []
        seen: set[Path] = set()

        for reldir in TICKET_DIRS:
            directory = self.artifacts_dir / reldir
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.md")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    raw = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    warnings.append(f"unreadable: {path}: {exc}")
                    continue
                frontmatter, _ = parse_frontmatter(raw)
                item_iteration = frontmatter.get("iteration")
                item_iteration = str(item_iteration) if item_iteration is not None else None
                if iteration_ref and item_iteration != iteration_ref:
                    continue
                items.append(
                    EstimableItem(
                        item_id=str(frontmatter.get("provider_id") or path.stem),
                        title=str(frontmatter.get("title") or path.stem),
                        item_type=str(frontmatter.get("work_item_type") or frontmatter.get("type") or ""),
                        points=_as_float(frontmatter.get("story_points")),
                        estimated_hours=_as_float(frontmatter.get("effort_hours")),
                        remaining_hours=_as_float(frontmatter.get("remaining_hours")),
                        completed_hours=_as_float(frontmatter.get("completed_hours")),
                        activity=str(frontmatter["activity"]) if frontmatter.get("activity") else None,
                        assigned_to=str(frontmatter["assigned_to"]) if frontmatter.get("assigned_to") else None,
                        state=str(frontmatter.get("state") or ""),
                        iteration=item_iteration,
                    )
                )

        if not items:
            warnings.append(f"no drafts found under {self.artifacts_dir}")
        return ProviderResult.success(items, warnings=tuple(warnings))

    # -- writes (planned, never performed) ---------------------------------

    def plan_hour_write(
        self,
        item_id: str,
        hours: float,
        *,
        activity: str | None = None,
        provenance: str = "",
    ) -> list[WriteOp]:
        ops = [
            WriteOp(
                item_id=item_id,
                field_path="frontmatter.effort_hours",
                value=hours,
                reason="estimated effort for this item",
                provenance=provenance,
            )
        ]
        if activity:
            ops.append(
                WriteOp(
                    item_id=item_id,
                    field_path="frontmatter.activity",
                    value=activity,
                    reason="activity classification",
                    provenance=provenance,
                )
            )
        return ops
