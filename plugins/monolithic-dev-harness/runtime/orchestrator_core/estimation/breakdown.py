"""Task-level estimation for one User Story.

This is what runs when a Story is decomposed into Tasks, and again whenever that Task list
changes. It derives hours for every Task from the Story's points, splits them so the parts
sum to the whole, and checks the total against the assigned person's remaining capacity in
the active sprint.

Two rules shape the behaviour:

**Recomputed hours are written without asking, and always reported.** A Task list that
changed but kept its old hours is worse than one with no hours, because the burndown keeps
charting a plan nobody is following. So a recompute applies itself -- and every change is
named in the summary, so nothing moves silently.

**Capacity is a ceiling, not a note.** When the derived hours exceed what the assignee has
left, the run stops and asks for a decision rather than writing an estimate that cannot fit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..capacity.planner import MemberAvailability
from .config import EstimationConfig
from .mapping import HourEstimate, distribute_hours, estimate_hours


# Every breakdown appends the same three tasks, and they are not the same size as the work
# they bracket. Splitting hours evenly across all of them would take real implementation time
# and hand it to a Done marker.
ROLE_IMPLEMENTATION = "implementation"
ROLE_STAGING = "staging"
ROLE_REVIEW = "review"
ROLE_BREAKDOWN = "breakdown"

DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    ROLE_IMPLEMENTATION: 1.0,
    ROLE_STAGING: 0.35,
    ROLE_REVIEW: 0.35,
    ROLE_BREAKDOWN: 0.0,  # a completion marker, not work -- carries no hours
}

# Recognised titles for the default tasks, English and pt-BR, since either may be used.
_ROLE_TITLES: dict[str, tuple[str, ...]] = {
    ROLE_STAGING: ("staging", "preparação", "preparacao", "preparo"),
    ROLE_REVIEW: ("review", "revisão", "revisao"),
    ROLE_BREAKDOWN: ("breakdown", "decomposição", "decomposicao"),
}


def task_role(title: str | None) -> str:
    """Classify a Task by title so the default tasks are not sized like real work."""
    text = (title or "").strip().casefold()
    if not text:
        return ROLE_IMPLEMENTATION
    for role, names in _ROLE_TITLES.items():
        if any(text == name or text.startswith(f"{name} ") or text.startswith(f"{name}:") for name in names):
            return role
    return ROLE_IMPLEMENTATION


@dataclass(frozen=True)
class TaskInput:
    """A Task as it exists before estimation."""

    task_id: str
    title: str = ""
    current_hours: float | None = None
    weight: float | None = None
    """Relative share of the Story's hours.

    Left unset, it is derived from the Task's role: implementation tasks carry the work,
    Staging and Review are lighter, and Breakdown is a marker that carries none. A caller
    that knows better -- having read the implementation plan -- should pass its own number.
    """

    @property
    def role(self) -> str:
        return task_role(self.title)

    @property
    def effective_weight(self) -> float:
        """The weight actually used: the caller's, or the one implied by the role."""
        if self.weight is not None:
            return max(0.0, self.weight)
        return DEFAULT_ROLE_WEIGHTS[self.role]


@dataclass(frozen=True)
class TaskEstimate:
    task_id: str
    title: str
    hours: float
    previous_hours: float | None = None
    role: str = ROLE_IMPLEMENTATION

    @property
    def changed(self) -> bool:
        previous = self.previous_hours if self.previous_hours is not None else 0.0
        return abs(previous - self.hours) >= 0.01

    @property
    def is_new(self) -> bool:
        return self.previous_hours is None

    def describe_change(self) -> str:
        if self.role == ROLE_BREAKDOWN and self.hours == 0:
            return f"{self.title or self.task_id}: no hours (completion marker)"
        if self.is_new:
            return f"{self.title or self.task_id}: — → {self.hours:g}h"
        arrow = "→" if self.changed else "="
        return f"{self.title or self.task_id}: {self.previous_hours:g}h {arrow} {self.hours:g}h"


@dataclass(frozen=True)
class BreakdownEstimate:
    """Hours for every Task under one Story, checked against the assignee's capacity."""

    story_id: str
    tasks: tuple[TaskEstimate, ...]
    total_hours: float
    provenance: str
    confidence: str
    assignee: str | None = None
    iteration_ref: str | None = None
    availability: MemberAvailability | None = None
    warnings: tuple[str, ...] = ()

    # -- capacity constraint ------------------------------------------------

    @property
    def capacity_known(self) -> bool:
        return self.availability is not None

    @property
    def remaining_hours(self) -> float | None:
        return self.availability.remaining_hours if self.availability else None

    @property
    def overflow_hours(self) -> float:
        """Hours by which this Story exceeds what the assignee has left. Zero when it fits."""
        remaining = self.remaining_hours
        if remaining is None:
            return 0.0
        return round(max(0.0, self.total_hours - remaining), 2)

    @property
    def blocked(self) -> bool:
        """True when the work cannot fit and a human decision is required before writing."""
        return self.overflow_hours > 0

    def resolution_options(self) -> tuple[str, ...]:
        """What a person can actually do about an overflow. Never decided automatically."""
        if not self.blocked:
            return ()
        return (
            "split the Story so part of it moves to a later sprint",
            "move the whole Story to a later sprint",
            "reassign it to someone with capacity left",
            "reduce the Task scope, then recompute",
        )

    # -- change reporting ---------------------------------------------------

    @property
    def changes(self) -> tuple[TaskEstimate, ...]:
        return tuple(t for t in self.tasks if t.changed)

    def describe(self) -> str:
        """The summary shown whenever estimates are computed or recomputed."""
        lines = [f"Task estimates — Story {self.story_id}"]
        if self.assignee:
            lines.append(f"  assignee : {self.assignee}")
        if self.iteration_ref:
            lines.append(f"  sprint   : {self.iteration_ref}")
        if self.availability:
            a = self.availability
            lines.append(
                f"  capacity : {a.remaining_hours:g}h left of {a.available_hours:g}h "
                f"({a.working_days} working days)"
            )
        else:
            lines.append("  capacity : unknown — not checked (see warnings)")

        lines.append("")
        for task in self.tasks:
            marker = "*" if task.changed else " "
            lines.append(f"  {marker} {task.describe_change()}")
        lines.append(f"    {'':<2}total: {self.total_hours:g}h  ({self.provenance})")

        if self.blocked:
            lines.append("")
            lines.append(f"  BLOCKED — exceeds remaining capacity by {self.overflow_hours:g}h.")
            lines.append("  Choose one before anything is written:")
            lines.extend(f"    - {option}" for option in self.resolution_options())
        elif self.changes:
            lines.append("")
            lines.append(f"  {len(self.changes)} estimate(s) changed and were updated.")

        for warning in self.warnings:
            lines.append(f"  ! {warning}")
        return "\n".join(lines)


def estimate_breakdown(
    story_id: str,
    story_points: float | None,
    tasks: list[TaskInput],
    *,
    config: EstimationConfig | None = None,
    calibration=None,
    assignee: str | None = None,
    iteration_ref: str | None = None,
    availability: MemberAvailability | None = None,
) -> BreakdownEstimate | None:
    """Derive hours for every Task under a Story and check them against capacity.

    Returns None when there is nothing to work from -- no points or no Tasks. An absent
    estimate is honest; a fabricated one is not.
    """
    if not tasks:
        return None

    config = config or EstimationConfig()
    story_estimate: HourEstimate | None = estimate_hours(
        story_points, config=config, calibration=calibration
    )
    if story_estimate is None:
        return None

    shares = distribute_hours(story_estimate.hours, [t.effective_weight for t in tasks])
    estimates = tuple(
        TaskEstimate(
            task_id=task.task_id,
            title=task.title,
            hours=hours,
            previous_hours=task.current_hours,
            role=task.role,
        )
        for task, hours in zip(tasks, shares)
    )

    warnings: list[str] = []
    if availability is None:
        warnings.append(
            "capacity not checked; the estimate has not been compared against anyone's availability"
        )
    if story_estimate.is_suggestion_only:
        warnings.append(
            f"hours derive from a {story_estimate.provenance} figure, not from this team's history"
        )

    return BreakdownEstimate(
        story_id=story_id,
        tasks=estimates,
        total_hours=round(sum(shares), 2),
        provenance=story_estimate.provenance,
        confidence=story_estimate.confidence,
        assignee=assignee,
        iteration_ref=iteration_ref,
        availability=availability,
        warnings=tuple(warnings),
    )


def recompute_breakdown(
    previous: BreakdownEstimate | None,
    current: BreakdownEstimate | None,
) -> tuple[TaskEstimate, ...]:
    """Tasks whose hours differ between two runs -- what a recompute report names.

    Comparing against the previous run rather than against stored values catches a Task that
    was removed and re-added at the same figure, which stored values alone would miss.
    """
    if current is None:
        return ()
    if previous is None:
        return current.tasks

    before = {t.task_id: t.hours for t in previous.tasks}
    changed: list[TaskEstimate] = []
    for task in current.tasks:
        was = before.get(task.task_id)
        if was is None or abs(was - task.hours) >= 0.01:
            changed.append(TaskEstimate(task.task_id, task.title, task.hours, was))
    return tuple(changed)
