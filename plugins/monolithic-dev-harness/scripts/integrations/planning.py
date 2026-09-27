"""The sprint model every tracker's planning operations speak, and the helpers they share.

Each tracker's `TrackerOps` (see `contracts.py`) turns what it knows about a sprint into these
values: the replies a skill fetched through the host's tools (Azure DevOps, Linear) or the
tracker's own files (local). Its `tracker.json` names the replies it needs under `planning`.
They read and plan only: a planned write is shown to a person before anything is recorded.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, value_or

# Saturday and Sunday. Azure DevOps lets a team configure its own weekend days; when that
# setting is unknown this is the assumption, and `IterationCapacity.weekend_days` overrides it.
DEFAULT_WEEKEND_DAYS = (5, 6)


def parse_date(value: Any) -> date | None:
    """An ISO date or datetime string as a date; None when there is none to read."""
    text = str(value or "").strip()
    return value_or(
        attempt(lambda: date.fromisoformat(text[:10]), "no_date", text, ValueError)
        if text
        else Ok(None),
        None,
    )


def as_float(value: Any) -> float | None:
    """A number from a reply or a file; None when the value is not one (a flag is not)."""
    match value:
        case bool():
            return None
        case int() | float():
            return float(value)
        case str():
            return value_or(
                attempt(lambda: float(value.strip()), "no_number", value, ValueError),
                None,
            )
        case _:
            return None


def first_number(record: Mapping[str, Any], *names: str) -> float | None:
    """The first of `names` holding a number. Not an `or` chain: a real 0 is falsy."""
    return next(
        (
            number
            for number in (as_float(record.get(name)) for name in names)
            if number is not None
        ),
        None,
    )


def date_ranges(raw: Any) -> tuple[DateRange, ...]:
    """Days off as ranges: `{start, end}` objects (end defaults to start) or single dates."""
    return tuple(
        DateRange(start, end)
        for start, end in (
            _bounds(entry) for entry in (raw if isinstance(raw, list) else ())
        )
        if start is not None and end is not None
    )


def _bounds(entry: Any) -> tuple[date | None, date | None]:
    match entry:
        case dict():
            start = parse_date(entry.get("start"))
            return start, parse_date(entry.get("end")) or start
        case str():
            day = parse_date(entry)
            return day, day
        case _:
            return None, None


@dataclass(frozen=True)
class DateRange:
    """An inclusive span of calendar days."""

    start: date
    end: date

    def days(self) -> list[date]:
        if self.end < self.start:
            return []
        span = (self.end - self.start).days
        return [self.start + timedelta(days=offset) for offset in range(span + 1)]

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class ActivityCapacity:
    """Hours per working day a person gives to one kind of work.

    An empty name is Azure's "unassigned activity" bucket, which is what a team that does
    not split capacity by activity ends up using.
    """

    name: str
    capacity_per_day: float

    @property
    def is_unassigned(self) -> bool:
        return not self.name.strip()


@dataclass(frozen=True)
class MemberCapacity:
    member_id: str
    display_name: str = ""
    activities: tuple[ActivityCapacity, ...] = ()
    days_off: tuple[DateRange, ...] = ()

    @property
    def daily_hours(self) -> float:
        return sum(a.capacity_per_day for a in self.activities)

    def is_off(self, day: date) -> bool:
        return any(r.contains(day) for r in self.days_off)


@dataclass(frozen=True)
class IterationCapacity:
    """A sprint's shape: when it runs, who is on it, and when nobody works."""

    iteration_ref: str
    start_date: date | None = None
    finish_date: date | None = None
    members: tuple[MemberCapacity, ...] = ()
    team_days_off: tuple[DateRange, ...] = ()
    weekend_days: tuple[int, ...] = DEFAULT_WEEKEND_DAYS

    def is_working_day(self, day: date) -> bool:
        if day.weekday() in self.weekend_days:
            return False
        return not any(r.contains(day) for r in self.team_days_off)

    def working_days(self) -> list[date]:
        if self.start_date is None or self.finish_date is None:
            return []
        return [
            d
            for d in DateRange(self.start_date, self.finish_date).days()
            if self.is_working_day(d)
        ]

    def working_days_for(self, member: MemberCapacity) -> list[date]:
        return [d for d in self.working_days() if not member.is_off(d)]


@dataclass(frozen=True)
class EstimableItem:
    """A work item as the capacity planner sees it, whatever system it came from."""

    item_id: str
    title: str = ""
    item_type: str = ""
    points: float | None = None
    estimated_hours: float | None = None
    remaining_hours: float | None = None
    completed_hours: float | None = None
    activity: str | None = None
    assigned_to: str | None = None
    state: str = ""
    iteration: str | None = None

    @property
    def planned_hours(self) -> float | None:
        """Hours this item puts on the sprint: remaining work if known, else the estimate."""
        if self.remaining_hours is not None:
            return self.remaining_hours
        return self.estimated_hours

    @property
    def has_estimate(self) -> bool:
        return self.planned_hours is not None


@dataclass(frozen=True)
class IterationReading:
    """A sprint read from provider replies, with anything the translation could not account for."""

    capacity: IterationCapacity
    warnings: tuple[str, ...] = ()


def empty_reading(iteration_ref: str, warning: str) -> IterationReading:
    return IterationReading(IterationCapacity(iteration_ref=iteration_ref), (warning,))


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
            for entry in _list(data.get("members"))
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
            for activity in _list(entry.get("activities"))
            if isinstance(activity, dict)
        ),
        days_off=date_ranges(entry.get("daysOff") or entry.get("days_off")),
    )


def _list(value: Any) -> tuple[Any, ...]:
    return tuple(value) if isinstance(value, list) else ()
