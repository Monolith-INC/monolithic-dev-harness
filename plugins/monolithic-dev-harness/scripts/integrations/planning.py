"""The sprint model every tracker's planning operations speak.

Each tracker's `TrackerOps` (see `contracts.py`) turns what it knows about a sprint into these
values: the replies a skill fetched through the host's tools (Azure DevOps, Linear) or the
tracker's own files (local). Its `tracker.json` names the replies it needs under `planning`.
They read and plan only: a planned write is shown to a person before anything is recorded.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .payloads import listed, named, one_or_many, parse_date

# Saturday and Sunday. Azure DevOps lets a team configure its own weekend days; when that
# setting is unknown this is the assumption, and `IterationCapacity.weekend_days` overrides it.
DEFAULT_WEEKEND_DAYS = (5, 6)

# The sprint reference that means "the active sprint"; an empty reference means the same.
CURRENT = "current"

HourFields = Callable[[float, bool], Mapping[str, float]]


def is_current(ref: str) -> bool:
    return ref.strip().lower() in ("", CURRENT)


def date_ranges(raw: Any) -> tuple[DateRange, ...]:
    """Days off as ranges: `{start, end}` objects (end defaults to start) or single dates."""
    return tuple(
        DateRange(start, end)
        for start, end in (_bounds(entry) for entry in listed(raw))
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


def pick_sprint(
    reply: Any,
    ref: str,
    markers: tuple[str, ...],
    keys: tuple[str, ...],
    active: Callable[[tuple[Mapping[str, Any], ...]], Mapping[str, Any] | None],
) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]:
    """The sprint a reply gives for `ref`, and a warning when it gives none.

    A single sprint (a record holding any of `markers`) is the one asked for. From a listing, the
    current sprint is `active(entries)` and any other reference the entry whose `keys` hold it.
    """
    entries = one_or_many(reply, *markers)
    sprint = (
        reply
        if entries == (reply,)
        else active(entries)
        if is_current(ref)
        else named(entries, ref, *keys)
    )
    return sprint, (
        ()
        if sprint is not None or reply is None
        else (
            "the reply has "
            + ("no current sprint" if is_current(ref) else f"no sprint {ref!r}")
            + ", so the sprint has no dates",
        )
    )


def no_hours(hours: float, first: bool) -> Mapping[str, float]:
    """How a tracker that records no hours records them: not at all."""
    return {}


def hour_writer(remaining: str, estimate: str = "") -> HourFields:
    """How a tracker records a task's hours: `remaining` always, and `estimate` (when the tracker
    has one) once, on the task's first non-zero figure."""
    return lambda hours, first: {
        remaining: hours,
        **({estimate: hours} if estimate and first and hours > 0 else {}),
    }
