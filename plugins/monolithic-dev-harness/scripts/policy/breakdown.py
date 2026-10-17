"""The Breakdown Task: generate-breakdown-work-items adds it last and sets it Done to mark that a
Story was broken down. It carries no work, so closing it needs no work session; it needs only that
the breakdown happened: it sits under a Story or Bug that holds the Story's other Tasks."""

from core.result import Result, bind, require
from integrations.contracts import BUILDABLE_KINDS, TrackerOps, WorkItem, WorkItemKind


def is_breakdown(item: WorkItem) -> bool:
    """The skill titles it `Breakdown` (kept recognizable when localized)."""
    return item.kind == WorkItemKind.TASK and item.title.strip().casefold().startswith(
        "breakdown"
    )


def closes(ops: TrackerOps, item: WorkItem) -> Result[None]:
    return bind(
        require(
            bool(item.parent_id),
            "workflow_policy",
            f"{item.key} has no parent Story",
        ),
        lambda _: bind(
            ops.get_work_item(item.parent_id),
            lambda parent: bind(
                require(
                    parent.kind in BUILDABLE_KINDS,
                    "workflow_policy",
                    f"the Breakdown Task {item.key} belongs under a Story or Bug",
                ),
                lambda _: bind(
                    ops.list_children(parent.id),
                    lambda children: require(
                        any(
                            child.kind == WorkItemKind.TASK and child.id != item.id
                            for child in children
                        ),
                        "workflow_policy",
                        f"[harness] {parent.key} has no Tasks besides {item.key}; create its "
                        "Tasks from the approved plan before marking the breakdown done",
                    ),
                ),
            ),
        ),
    )
