"""What makes a file the implementation plan `implementation-confirm` may be asked about.

The question is about exactly one note of type `implementation-plan`, marked `status: approved` so
the approval pins it, that names exactly one Story or Bug, and that Story or Bug exists in the
selected tracker. The Story comes from the plan, so the agent never names it separately. That the
plan was shown first is the gate's own `shown` rule (`artifact_review`).
"""

from __future__ import annotations

from pathlib import Path

from core.result import Ok, Result, bind, err
from harness import local_artifacts
from harness.workflow_requirements import artifact_kind
from integrations.contracts import BUILDABLE_KINDS, TrackerOps


def story(repo: Path, names: list[str]) -> Result[str]:
    """The Story or Bug the one approved plan in `names` is for."""
    match names:
        case [name]:
            return _plan_story(name, local_artifacts.note((repo / name).resolve()))
        case _:
            return err(
                "plan_invalid",
                "name one implementation plan with --artifact; each Story's plan is approved "
                "on its own",
            )


def tracked(ops: TrackerOps, key: str) -> Result[None]:
    """The plan's Story or Bug exists in the tracker."""
    return bind(
        ops.get_work_item(key),
        lambda item: (
            Ok(None)
            if item.kind in BUILDABLE_KINDS
            else err(
                "plan_invalid",
                f"{key} is a {item.kind.value}; a plan is approved for a Story or Bug",
            )
        ),
    )


def _plan_story(name: str, note: local_artifacts.Note | None) -> Result[str]:
    match note:
        case None:
            return err("plan_invalid", f"{name} is not a file in this project")
        case local_artifacts.Note() if (
            artifact_kind(note.kind) != "implementation_plan"
        ):
            return err(
                "plan_invalid", f"{name} is not a note of type implementation-plan"
            )
        case local_artifacts.Note() if not note.approved:
            return err(
                "plan_invalid",
                f"set `status: approved` in {name} before asking, so the approval pins it",
            )
        case local_artifacts.Note(work_items=(key,)):
            return Ok(key)
        case _:
            return err(
                "plan_invalid",
                f"{name} must name exactly one Story or Bug in `story`; it names "
                f"{', '.join(note.work_items) or 'none'}",
            )
