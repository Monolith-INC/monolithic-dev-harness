"""Generic sprint-capacity core.

Answers "does this sprint fit?" from a provider-agnostic model of an iteration: who is on
the team, how many hours a day each gives, when nobody works, and what has been taken on.

Pure and I/O-free, like `estimation`. Its inputs are the planning values in
`integrations.planning`, which a tracker's planning capability (or the user's planning files)
produces; nothing here knows what Azure DevOps is.
"""

from __future__ import annotations

from integrations.planning import (
    ActivityCapacity,
    DateRange,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
    parse_date,
)

from .model import ActivityBreakdown, CapacityPlan
from .planner import (
    UNASSIGNED_ACTIVITY,
    MemberAvailability,
    availability_for,
    available_by_activity,
    available_hours,
    find_member,
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
