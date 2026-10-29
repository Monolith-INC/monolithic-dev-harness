"""What makes a file the implementation plan `implementation-confirm` may be asked about.

The question is about exactly one note of type `implementation-plan` in the artifacts path, which the
approval pins, that names exactly one Story or Bug, and that Story or Bug exists in the
selected tracker and is refined (it passes `validate-artifact`): the toolkit writes a Story's plan
from its refined acceptance criteria. The Story comes from the plan, so the agent never names it separately. That the
plan was shown first is the gate's own `shown` rule (`artifact_review`).
"""

from __future__ import annotations

from pathlib import Path

from core.result import Ok, Result, bind, err
from harness import local_artifacts, refined, work_sessions
from harness.workflow_requirements import artifact_kind
from integrations.contracts import BUILDABLE_KINDS, TrackerOps


def story(repo: Path, names: list[str]) -> Result[str]:
    """The Story or Bug the one approved plan in `names` is for."""
    match names:
        case [name] if not _in_artifacts_path(repo, name):
            return err(
                "plan_invalid",
                f"{name} is outside the artifacts path, so approving it could not pin it; save "
                "the plan in the artifacts path",
            )
        case [name]:
            return _plan_story(name, local_artifacts.note((repo / name).resolve()))
        case _:
            return err(
                "plan_invalid",
                "name one implementation plan with --artifact; each Story's plan is approved "
                "on its own",
            )


def tracked(ops: TrackerOps, key: str) -> Result[None]:
    """The plan's Story or Bug exists in the tracker and is refined."""
    return bind(
        ops.get_work_item(key),
        lambda item: (
            refined.check(item)
            if item.kind in BUILDABLE_KINDS
            else err(
                "plan_invalid",
                f"{key} is a {item.kind.value}; a plan is approved for a Story or Bug",
            )
        ),
    )


def source_matches(
    repo: Path, names: list[str], ops: TrackerOps, scope: str | None = None
) -> Result[None]:
    from harness.workflow_evidence import item_digest

    match names, scope or work_sessions.current(repo):
        case [name], scope if scope:
            match local_artifacts.note((repo / name).resolve()):
                case local_artifacts.Note() as note if len(note.work_items) == 1:
                    return bind(
                        ops.get_work_item(note.work_items[0]),
                        lambda item: (
                            Ok(None)
                            if note.frontmatter.get("source_digest")
                            == item_digest(item)
                            else err(
                                "plan_source_changed",
                                "The plan must name source_digest for the current verified work-item requirements; regenerate or revalidate it after enrichment before approval.",
                            )
                        ),
                    )
                case _:
                    return err("plan_invalid", "Plan must name exactly one work item")
        case _:
            return Ok(None)


def approved_source(repo: Path, item) -> bool:
    from harness import state
    from harness.workflow_evidence import item_digest

    return any(
        note.digest in digests
        and note.kind == "implementation-plan"
        and item.key in note.work_items
        and note.frontmatter.get("source_digest") == item_digest(item)
        for path, digests in state.pinned_notes(repo).items()
        for note in (local_artifacts.note(Path(path)),)
        if note is not None
    )


def _in_artifacts_path(repo: Path, name: str) -> bool:
    folder = local_artifacts.artifacts_dir(repo)
    return folder is not None and (repo / name).resolve().is_relative_to(
        folder.resolve()
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
        case local_artifacts.Note(work_items=(key,)):
            return Ok(key)
        case _:
            return err(
                "plan_invalid",
                f"{name} must name exactly one Story or Bug in `story`; it names "
                f"{', '.join(note.work_items) or 'none'}",
            )
