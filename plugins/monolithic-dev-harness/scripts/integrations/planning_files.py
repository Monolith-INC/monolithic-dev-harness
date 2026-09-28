"""The formats a person writes for planning, shared by the planning-files source and the local tracker.

A planning item's fields (in a draft's front matter, or a local tracker record) and the capacity
file each have one definition and one reader, here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err

from .payloads import as_float, as_text, first_number, listed, parse_date
from .planning import (
    ActivityCapacity,
    EstimableItem,
    IterationCapacity,
    IterationReading,
    MemberCapacity,
    date_ranges,
    empty_reading,
    hour_writer,
)

# A planning item's fields. One format, read by `planning_item` alone.
POINTS = "story_points"
ESTIMATED_HOURS = "effort_hours"
REMAINING_HOURS = "remaining_hours"
COMPLETED_HOURS = "completed_hours"
ACTIVITY = "activity"
ASSIGNED_TO = "assigned_to"
ITERATION = "iteration"
STATE = "state"


def planning_item(
    item_id: str, title: str, item_type: str, fields: Mapping[str, Any]
) -> EstimableItem:
    return EstimableItem(
        item_id=item_id,
        title=title,
        item_type=item_type,
        points=as_float(fields.get(POINTS)),
        estimated_hours=as_float(fields.get(ESTIMATED_HOURS)),
        remaining_hours=as_float(fields.get(REMAINING_HOURS)),
        completed_hours=as_float(fields.get(COMPLETED_HOURS)),
        activity=as_text(fields.get(ACTIVITY)) or None,
        assigned_to=as_text(fields.get(ASSIGNED_TO)) or None,
        state=as_text(fields.get(STATE)),
        iteration=as_text(fields.get(ITERATION)) or None,
    )


# How a planning item records a task's hours.
RECORDED_HOURS = hour_writer(REMAINING_HOURS, ESTIMATED_HOURS)


# The capacity file a person writes, for the planning-files source and the local tracker alike:
#   {"startDate": "...", "finishDate": "...", "teamDaysOff": [...],
#    "members": [{"id", "name", "daysOff": [...], "activities": [{"name", "capacityPerDay"}]}]}
# snake_case spellings (start_date, capacity_per_day, ...) are read too.


def read_capacity_file(path: Path, iteration_ref: str) -> Result[IterationReading]:
    """The sprint a capacity file describes. No file is a sprint with no team or dates; a file
    that cannot be read is an error, because saying "no file" would send someone the wrong way.
    """
    return (
        bind(
            attempt(
                lambda: json.loads(path.read_text(encoding="utf-8")),
                "unreadable_capacity",
                f"capacity file unreadable: {path}",
                OSError,
                ValueError,
            ),
            lambda data: (
                Ok(IterationReading(capacity_document(iteration_ref, data)))
                if isinstance(data, dict)
                else err(
                    "unreadable_capacity", f"capacity file is not an object: {path}"
                )
            ),
        )
        if path.is_file()
        else Ok(
            empty_reading(
                iteration_ref,
                f"no capacity file at {path}; iteration has no team or dates",
            )
        )
    )


def capacity_document(iteration_ref: str, data: Mapping[str, Any]) -> IterationCapacity:
    return IterationCapacity(
        iteration_ref=iteration_ref,
        start_date=parse_date(data.get("startDate") or data.get("start_date")),
        finish_date=parse_date(data.get("finishDate") or data.get("finish_date")),
        members=tuple(
            _member(entry)
            for entry in listed(data.get("members"))
            if isinstance(entry, dict)
        ),
        team_days_off=date_ranges(data.get("teamDaysOff") or data.get("team_days_off")),
    )


def _member(entry: Mapping[str, Any]) -> MemberCapacity:
    return MemberCapacity(
        member_id=str(entry.get("id") or entry.get("name") or ""),
        display_name=str(entry.get("name") or entry.get("id") or ""),
        activities=tuple(
            ActivityCapacity(
                str(activity.get("name", "")),
                first_number(activity, "capacityPerDay", "capacity_per_day") or 0.0,
            )
            for activity in listed(entry.get("activities"))
            if isinstance(activity, dict)
        ),
        days_off=date_ranges(entry.get("daysOff") or entry.get("days_off")),
    )
