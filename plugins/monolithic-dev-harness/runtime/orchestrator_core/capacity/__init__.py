"""Generic sprint-capacity core.

Answers "does this sprint fit?" from a provider-agnostic model of an iteration: who is on
the team, how many hours a day each gives, when nobody works, and what has been taken on.

Pure and I/O-free, like `estimation`. Providers translate their own shapes into
`IterationCapacity` and `EstimableItem`; nothing here knows what Azure DevOps is.
"""

from __future__ import annotations

from .model import (
    ActivityBreakdown,
    ActivityCapacity,
    CapacityPlan,
    DateRange,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
    parse_date,
)
from .planner import (
    find_member,
    UNASSIGNED_ACTIVITY,
    MemberAvailability,
    availability_for,
    available_by_activity,
    available_hours,
    format_plan,
    plan_iteration,
    planned_by_activity,
)

__all__ = [
    "ActivityBreakdown",
    "ActivityCapacity",
    "CapacityPlan",
    "DateRange",
    "EstimableItem",
    "IterationCapacity",
    "MemberAvailability",
    "MemberCapacity",
    "UNASSIGNED_ACTIVITY",
    "availability_for",
    "available_by_activity",
    "available_hours",
    "find_member",
    "format_plan",
    "parse_date",
    "plan_iteration",
    "planned_by_activity",
]
