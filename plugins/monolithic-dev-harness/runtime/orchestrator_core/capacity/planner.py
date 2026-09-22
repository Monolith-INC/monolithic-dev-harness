from __future__ import annotations

from dataclasses import dataclass

from .model import (
    ActivityBreakdown,
    CapacityPlan,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
)

UNASSIGNED_ACTIVITY = "(unassigned)"


@dataclass(frozen=True)
class MemberAvailability:
    """One person's hours in one iteration -- the figure a Task estimate is checked against."""

    member_id: str
    display_name: str
    available_hours: float
    working_days: int
    days_off: int
    committed_hours: float = 0.0
    """Hours already on this person's other items in the same iteration."""

    @property
    def remaining_hours(self) -> float:
        return round(self.available_hours - self.committed_hours, 2)


def _normalise(value: str | None) -> str:
    return (value or "").strip().casefold()


def _identities(member: MemberCapacity) -> set[str]:
    """Every form this person may be referred to by, normalised.

    Azure identifies people by GUID in capacity data and by display or unique name on work
    items, so the two sides routinely disagree. Comparing whole identity sets keeps a person
    recognisable whichever form each payload happened to use.
    """
    forms = {_normalise(member.member_id), _normalise(member.display_name)}
    for value in (member.member_id, member.display_name):
        local = _normalise(value).split("@", 1)[0]
        if local:
            forms.add(local)
    forms.discard("")
    return forms


def find_member(iteration: IterationCapacity, reference: str | None) -> MemberCapacity | None:
    """Match a work-item assignee to a team member.

    Tries the id, the display name, and the local part of an email-style unique name.
    Returns None rather than guessing when nothing matches -- an unmatched assignee must be
    reported, not silently attributed.
    """
    wanted = _normalise(reference)
    if not wanted:
        return None
    candidates = {wanted, wanted.split("@", 1)[0]}
    for member in iteration.members:
        if _identities(member) & candidates:
            return member
    return None


def availability_for(
    iteration: IterationCapacity,
    reference: str | None,
    *,
    items: list[EstimableItem] | None = None,
) -> MemberAvailability | None:
    """Hours one person has in this iteration, less what is already on their plate.

    `items` are the iteration's other work items; anything already assigned to this person
    counts against their capacity, so a second Story is checked against what is actually left.
    """
    member = find_member(iteration, reference)
    if member is None:
        return None

    present_days = iteration.working_days_for(member)

    # Match each item back to a member rather than comparing raw strings: the item may name
    # the person differently from the capacity payload, and treating that as "someone else"
    # would report their whole existing load as free capacity.
    committed = 0.0
    for item in items or []:
        if find_member(iteration, item.assigned_to) is not member:
            continue
        hours = item.planned_hours
        if hours:
            committed += hours

    return MemberAvailability(
        member_id=member.member_id,
        display_name=member.display_name or member.member_id,
        available_hours=round(member.daily_hours * len(present_days), 2),
        working_days=len(present_days),
        days_off=len(iteration.working_days()) - len(present_days),
        committed_hours=round(committed, 2),
    )


def available_hours(iteration: IterationCapacity) -> float:
    """Total hours the team can give this sprint.

    Each member's daily capacity multiplied by the days they are actually present -- team
    days off, personal days off, and weekends all removed.
    """
    total = 0.0
    for member in iteration.members:
        days = len(iteration.working_days_for(member))
        total += member.daily_hours * days
    return round(total, 2)


def available_by_activity(iteration: IterationCapacity) -> dict[str, float]:
    """Available hours split by activity, using Azure's per-activity capacity model."""
    totals: dict[str, float] = {}
    for member in iteration.members:
        days = len(iteration.working_days_for(member))
        if not days:
            continue
        for activity in member.activities:
            key = UNASSIGNED_ACTIVITY if activity.is_unassigned else activity.name
            totals[key] = round(totals.get(key, 0.0) + activity.capacity_per_day * days, 2)
    return totals


def planned_by_activity(items: list[EstimableItem]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in items:
        hours = item.planned_hours
        if hours is None:
            continue
        key = item.activity.strip() if item.activity and item.activity.strip() else UNASSIGNED_ACTIVITY
        totals[key] = round(totals.get(key, 0.0) + hours, 2)
    return totals


def _build_warnings(
    *,
    iteration: IterationCapacity,
    plan_available: float,
    plan_planned: float,
    items_total: int,
    items_estimated: int,
) -> tuple[str, ...]:
    warnings: list[str] = []

    if iteration.start_date is None or iteration.finish_date is None:
        warnings.append("iteration has no start/finish date; available hours cannot be computed")
    if not iteration.members:
        warnings.append("iteration has no team members with capacity set")
    if plan_available <= 0:
        warnings.append("available capacity is zero; utilisation is undefined")

    unestimated = items_total - items_estimated
    if unestimated:
        warnings.append(
            f"{unestimated} of {items_total} items carry no estimate; planned hours are a floor, not a total"
        )
    if items_total and items_estimated == 0:
        warnings.append("no item carries an estimate; this plan says nothing about fit")

    if plan_available > 0 and plan_planned > plan_available:
        over = round(plan_planned - plan_available, 2)
        warnings.append(f"overcommitted by {over:g}h ({plan_planned:g}h planned vs {plan_available:g}h available)")

    return tuple(warnings)


def plan_iteration(
    iteration: IterationCapacity,
    items: list[EstimableItem] | None = None,
) -> CapacityPlan:
    """Compare what the team can do against what it has taken on.

    Pure function over the generic model -- it knows nothing about Azure DevOps or any
    other provider. Never raises; missing data surfaces as warnings on the returned plan.
    """
    items = items or []
    avail_total = available_hours(iteration)
    avail_activities = available_by_activity(iteration)
    planned_activities = planned_by_activity(items)
    planned_total = round(sum(planned_activities.values()), 2)

    estimated = sum(1 for i in items if i.has_estimate)

    activities = sorted(set(avail_activities) | set(planned_activities))
    breakdown = tuple(
        ActivityBreakdown(
            activity=name,
            available_hours=avail_activities.get(name, 0.0),
            planned_hours=planned_activities.get(name, 0.0),
        )
        for name in activities
    )

    return CapacityPlan(
        iteration_ref=iteration.iteration_ref,
        available_hours=avail_total,
        planned_hours=planned_total,
        working_days=len(iteration.working_days()),
        member_count=len(iteration.members),
        items_total=len(items),
        items_estimated=estimated,
        by_activity=breakdown,
        warnings=_build_warnings(
            iteration=iteration,
            plan_available=avail_total,
            plan_planned=planned_total,
            items_total=len(items),
            items_estimated=estimated,
        ),
    )


def format_plan(plan: CapacityPlan) -> str:
    """Terminal report, matching the plain style of report_formatter."""
    lines = [
        f"Capacity plan: {plan.iteration_ref}",
        "=" * 60,
        f"  Working days   : {plan.working_days}",
        f"  Team members   : {plan.member_count}",
        f"  Available      : {plan.available_hours:g}h",
        f"  Planned        : {plan.planned_hours:g}h",
    ]

    util = plan.utilisation
    lines.append(f"  Utilisation    : {util * 100:.0f}%" if util is not None else "  Utilisation    : n/a")

    coverage = plan.coverage
    if coverage is not None:
        lines.append(
            f"  Estimated      : {plan.items_estimated}/{plan.items_total} items ({coverage * 100:.0f}%)"
        )

    if plan.by_activity:
        lines.append("")
        lines.append("  By activity:")
        for row in plan.by_activity:
            row_util = row.utilisation
            suffix = f" ({row_util * 100:.0f}%)" if row_util is not None else ""
            lines.append(
                f"    {row.activity:<20} {row.planned_hours:>7g}h planned / {row.available_hours:>7g}h available{suffix}"
            )

    if plan.warnings:
        lines.append("")
        lines.append("  Warnings:")
        lines.extend(f"    - {w}" for w in plan.warnings)

    return "\n".join(lines)
