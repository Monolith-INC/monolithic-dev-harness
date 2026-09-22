from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Saturday and Sunday. Azure DevOps lets a team configure its own weekend days; when that
# setting is unknown this is the assumption, and `IterationCapacity.weekend_days` overrides it.
DEFAULT_WEEKEND_DAYS = (5, 6)


def parse_date(value: str | None) -> date | None:
    """Parse an ISO date or datetime string to a date, degrading to None."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


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
        return [d for d in DateRange(self.start_date, self.finish_date).days() if self.is_working_day(d)]

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
class ActivityBreakdown:
    activity: str
    available_hours: float
    planned_hours: float

    @property
    def utilisation(self) -> float | None:
        if self.available_hours <= 0:
            return None
        return self.planned_hours / self.available_hours


@dataclass(frozen=True)
class CapacityPlan:
    """The answer to 'does this sprint fit?'."""

    iteration_ref: str
    available_hours: float
    planned_hours: float
    working_days: int
    member_count: int
    items_total: int
    items_estimated: int
    by_activity: tuple[ActivityBreakdown, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def utilisation(self) -> float | None:
        if self.available_hours <= 0:
            return None
        return self.planned_hours / self.available_hours

    @property
    def overcommitted(self) -> bool:
        util = self.utilisation
        return util is not None and util > 1.0

    @property
    def items_unestimated(self) -> int:
        return self.items_total - self.items_estimated

    @property
    def coverage(self) -> float | None:
        """Share of items carrying an estimate. A plan built on 20% coverage means little."""
        if self.items_total <= 0:
            return None
        return self.items_estimated / self.items_total
