"""Pure translation between Azure DevOps JSON and the generic capacity model.

No I/O lives here by design: every function takes already-decoded JSON, so the real logic
is testable against captured fixtures without touching the network. This mirrors the
existing precedent of `ingest_azure_record`, which is a constructor that fetches nothing.
"""

from __future__ import annotations

from typing import Any

from ...capacity.model import (
    ActivityCapacity,
    DateRange,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
    parse_date,
)
from . import fields as f

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _weekday_index(value: Any) -> int | None:
    """Normalise one working-day entry to Python's weekday numbering (Monday = 0).

    Azure sends day names through the REST API but plain integers through the MCP server,
    and those integers use the JavaScript convention where Sunday is 0. Python counts from
    Monday, so the integers need shifting -- a team working [1,2,3,4,5] means Monday to
    Friday, not Tuesday to Saturday.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return (value - 1) % 7 if 0 <= value <= 6 else None
    text = str(value).strip().lower()
    if text.isdigit():
        number = int(text)
        return (number - 1) % 7 if 0 <= number <= 6 else None
    return WEEKDAY_INDEX.get(text)


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


def _first_present(raw_fields: dict[str, Any], *names: str) -> float | None:
    """First field that is actually present, in preference order.

    Deliberately not an `or` chain: a legitimate 0 is falsy, so `or` would both discard an
    explicit zero and fall through to another process's field.
    """
    for name in names:
        value = _as_float(raw_fields.get(name))
        if value is not None:
            return value
    return None


# Keys an Azure list can hide behind, in preference order. The raw REST API uses the
# {count, value} envelope; the Azure DevOps MCP server reshapes some responses under a
# named key instead -- capacity comes back as {teamMembers, totalCapacityPerDay, ...}.
# Both paths are supported, so both envelopes must be understood.
LIST_KEYS = ("value", "teamMembers", "workItems", "iterations", "values")


def _unwrap(payload: Any) -> list[dict[str, Any]]:
    """Accept a bare list, the {count, value} envelope, or a named-key envelope."""
    if isinstance(payload, dict):
        for key in LIST_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                payload = candidate
                break
        else:
            return []
    if not isinstance(payload, list):
        return []
    return [entry for entry in payload if isinstance(entry, dict)]


def map_days_off(payload: Any) -> tuple[DateRange, ...]:
    """Map a daysOff array. Accepts the bare list or the {daysOff: [...]} envelope."""
    if isinstance(payload, dict):
        payload = payload.get("daysOff", [])
    out: list[DateRange] = []
    for entry in payload if isinstance(payload, list) else []:
        if not isinstance(entry, dict):
            continue
        start = parse_date(entry.get("start"))
        end = parse_date(entry.get("end")) or start
        if start and end:
            out.append(DateRange(start, end))
    return tuple(out)


def map_capacities(payload: Any) -> tuple[MemberCapacity, ...]:
    """Map the teamsettings/iterations/{id}/capacities response."""
    members: list[MemberCapacity] = []
    for entry in _unwrap(payload):
        team_member = entry.get("teamMember") if isinstance(entry.get("teamMember"), dict) else {}
        activities = []
        for activity in entry.get("activities", []):
            if not isinstance(activity, dict):
                continue
            per_day = _as_float(activity.get("capacityPerDay"))
            if per_day is None:
                # Unreadable is not zero. Skipping keeps it out of the sum, and the
                # totalCapacityPerDay cross-check below will catch the shortfall.
                continue
            activities.append(
                ActivityCapacity(name=str(activity.get("name", "") or ""), capacity_per_day=per_day)
            )
        activities = tuple(activities)
        members.append(
            MemberCapacity(
                member_id=str(team_member.get("id", "") or ""),
                display_name=str(team_member.get("displayName", "") or ""),
                activities=activities,
                days_off=map_days_off(entry.get("daysOff")),
            )
        )
    return tuple(members)


# Azure's iteration timeFrame enum: 0 past, 1 current, 2 future.
TIMEFRAME_CURRENT = 1


def current_iteration(payload: Any) -> dict[str, Any] | None:
    """The active sprint from an iteration listing, or None when none is active.

    A `$timeframe=current` query returns only the active one, so a single entry is taken as
    current. Otherwise the `attributes.timeFrame` marker selects it.
    """
    entries = _unwrap(payload)
    if not entries:
        return None
    unmarked = []
    for entry in entries:
        attributes = entry.get("attributes") if isinstance(entry.get("attributes"), dict) else {}
        marker = attributes.get("timeFrame")
        if marker == TIMEFRAME_CURRENT:
            return entry
        if marker is None:
            unmarked.append(entry)
    # A `$timeframe=current` query returns only the active sprint, so a single unmarked
    # entry is it. An entry marked past or future is never treated as current.
    return unmarked[0] if len(unmarked) == 1 and len(entries) == 1 else None


def reported_daily_total(payload: Any) -> float | None:
    """Azure's own `totalCapacityPerDay`, when the payload carries it.

    Free cross-check: if the summed per-member capacity disagrees with this, the mapping
    dropped or misread someone. Returns None when the payload does not report a total.
    """
    if not isinstance(payload, dict):
        return None
    return _as_float(payload.get("totalCapacityPerDay"))


def map_weekend_days(team_settings: Any) -> tuple[int, ...] | None:
    """Derive weekend days from a team's configured workingDays.

    Azure states which days are worked; the model wants the complement.

    Returns None for "not stated" -- absent settings, or entries none of which could be read
    -- so the caller keeps its default. An empty tuple is a real answer: a team that works
    all seven days has no weekend, and collapsing that into "unknown" would silently delete
    two days of their capacity.
    """
    if not isinstance(team_settings, dict):
        return None
    working = team_settings.get("workingDays")
    if not isinstance(working, list) or not working:
        return None
    worked = {index for index in (_weekday_index(d) for d in working) if index is not None}
    if not worked:
        return None
    return tuple(sorted(set(range(7)) - worked))


def map_iteration(
    iteration_ref: str,
    *,
    iteration: Any = None,
    capacities: Any = None,
    team_settings: Any = None,
) -> IterationCapacity:
    """Assemble an IterationCapacity from the three Azure payloads that describe a sprint."""
    start = finish = None
    if isinstance(iteration, dict):
        attributes = iteration.get("attributes") if isinstance(iteration.get("attributes"), dict) else {}
        start = parse_date(attributes.get("startDate") or iteration.get("startDate"))
        finish = parse_date(attributes.get("finishDate") or iteration.get("finishDate"))

    weekend = map_weekend_days(team_settings)
    team_days_off = ()
    if isinstance(team_settings, dict):
        team_days_off = map_days_off(team_settings.get("teamDaysOff"))

    kwargs: dict[str, Any] = {
        "iteration_ref": iteration_ref,
        "start_date": start,
        "finish_date": finish,
        "members": map_capacities(capacities),
        "team_days_off": team_days_off,
    }
    if weekend is not None:
        kwargs["weekend_days"] = weekend
    return IterationCapacity(**kwargs)


def map_work_item(payload: Any, *, process: str | None = None) -> EstimableItem | None:
    """Map one work item. Returns None when the payload carries no usable id."""
    if not isinstance(payload, dict):
        return None
    raw_fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
    item_id = payload.get("id") or raw_fields.get("System.Id")
    if item_id is None:
        return None

    assigned = raw_fields.get(f.ASSIGNED_TO)
    if isinstance(assigned, dict):
        assigned = assigned.get("displayName") or assigned.get("uniqueName")

    activity = raw_fields.get(f.activity_field(process)) or raw_fields.get(f.ACTIVITY)

    return EstimableItem(
        item_id=str(item_id),
        title=str(raw_fields.get(f.TITLE, "") or ""),
        item_type=str(raw_fields.get(f.WORK_ITEM_TYPE, "") or ""),
        points=_first_present(raw_fields, f.points_field(process), f.STORY_POINTS, f.EFFORT, f.SIZE),
        estimated_hours=_as_float(raw_fields.get(f.ORIGINAL_ESTIMATE)),
        remaining_hours=_as_float(raw_fields.get(f.REMAINING_WORK)),
        completed_hours=_as_float(raw_fields.get(f.COMPLETED_WORK)),
        activity=str(activity) if activity else None,
        assigned_to=str(assigned) if assigned else None,
        state=str(raw_fields.get(f.STATE, "") or ""),
        iteration=str(raw_fields.get(f.ITERATION_PATH, "") or "") or None,
    )


def map_work_items(payload: Any, *, process: str | None = None) -> list[EstimableItem]:
    items = [map_work_item(entry, process=process) for entry in _unwrap(payload)]
    return [item for item in items if item is not None]
