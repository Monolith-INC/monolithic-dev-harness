"""What the capacity planner answers: available against planned hours, per activity."""

from __future__ import annotations

from dataclasses import dataclass, field


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
