"""What makes a file the implementation plan `implementation-confirm` may be asked about.

The question is about exactly one note of type `implementation-plan` in the artifacts path, which the
approval pins, that names exactly one Story or Bug, and that Story or Bug exists in the
selected tracker and is refined (it passes `validate-artifact`): the toolkit writes a Story's plan
from its refined acceptance criteria. The Story comes from the plan, so the agent never names it separately. That the
plan was shown first is the gate's own `shown` rule (`artifact_review`).

The checks that read the tracker run in a CLI command, never in a hook: when the question is
prepared (`harness decision present`) and on `harness plan check <story>`. A run that passes
leaves a receipt in `.harness/state/plan-receipts/`, keyed by the Story: the digest of the Story's
requirements, the digest of the plan, and the time. The hooks read that receipt (`unchecked`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.result import Err, Ok, Result, attempt, bind, err, fmap
from harness import local_artifacts, refined, state, work_sessions
from harness.workflow_requirements import artifact_kind
from integrations.contracts import BUILDABLE_KINDS, TrackerOps, WorkItem

RECEIPTS = "plan-receipts"


def story(repo: Path, names: list[str]) -> Result[str]:
    """The Story or Bug the one approved plan in `names` is for."""
    return fmap(_plan_snapshot(repo, names), lambda snapshot: snapshot[0])


def _plan_snapshot(
    repo: Path, names: list[str]
) -> Result[tuple[str, local_artifacts.Note]]:
    """Read and validate the plan once, preserving the exact content that was checked."""
    match names:
        case [name] if not _in_artifacts_path(repo, name):
            return err(
                "plan_invalid",
                f"{name} is outside the artifacts path, so approving it could not pin it; save "
                "the plan in the artifacts path",
            )
        case [name]:
            match local_artifacts.note((repo / name).resolve()):
                case local_artifacts.Note() as note:
                    return fmap(_plan_story(name, note), lambda key: (key, note))
                case None:
                    return err("plan_invalid", f"{name} is not a file in this project")
        case _:
            return err(
                "plan_invalid",
                "name one implementation plan with --artifact; each Story's plan is approved "
                "on its own",
            )


def tracked(ops: TrackerOps, key: str) -> Result[None]:
    """The plan's Story or Bug exists in the tracker and is refined."""
    return bind(ops.get_work_item(key), _refined_item)


def _refined_item(item: WorkItem) -> Result[None]:
    return (
        refined.check(item)
        if item.kind in BUILDABLE_KINDS
        else err(
            "plan_invalid",
            f"{item.key} is a {item.kind.value}; a plan is approved for a Story or Bug",
        )
    )


def _matching_source(note: local_artifacts.Note, item: WorkItem) -> Result[None]:
    from harness.workflow_evidence import item_digest

    return (
        Ok(None)
        if note.frontmatter.get("source_digest") == item_digest(item)
        else err(
            "plan_source_changed",
            "The plan must name source_digest for the current verified work-item requirements; regenerate or revalidate it after enrichment before approval.",
        )
    )


def source_matches(
    repo: Path, names: list[str], ops: TrackerOps, scope: str | None = None
) -> Result[None]:
    match names, scope or work_sessions.current(repo):
        case [name], scope if scope:
            match local_artifacts.note((repo / name).resolve()):
                case local_artifacts.Note() as note if len(note.work_items) == 1:
                    return bind(
                        ops.get_work_item(note.work_items[0]),
                        lambda item: _matching_source(note, item),
                    )
                case _:
                    return err("plan_invalid", "Plan must name exactly one work item")
        case _:
            return Ok(None)


def verify(
    repo: Path, names: list[str], ops: TrackerOps, scope: str | None = None
) -> Result[str]:
    """The Story of the one plan in `names`, once the tracker confirms it is refined and the plan
    was written from its current requirements. Passing leaves the plan's receipt."""
    check_source = bool(scope or work_sessions.current(repo))
    match _plan_snapshot(repo, names):
        case Err() as failure:
            return failure
        case Ok((key, note)):
            pass
    return bind(
        ops.get_work_item(key),
        lambda item: bind(
            _refined_item(item),
            lambda _: bind(
                _matching_source(note, item) if check_source else Ok(None),
                lambda _: fmap(
                    _write_receipt(repo, key, names[0], note.digest, item),
                    lambda _: key,
                ),
            ),
        ),
    )


def recheck(repo: Path, key: str, ops: TrackerOps) -> Result[dict]:
    """Read the tracker again for the plan of the Story `key` and write a fresh receipt. A plan
    that no longer passes keeps no receipt."""
    match bind(_plan_of(repo, key), lambda name: verify(repo, [name], ops)):
        case Ok():
            return Ok(receipt(repo, key) or {})
        case Err() as failure:
            attempt(
                lambda: _receipt_path(repo, key).unlink(missing_ok=True),
                "state_unwritable",
                "plan receipt",
                OSError,
                ValueError,
            )
            return failure


def receipt(repo: Path, key: str) -> dict | None:
    """The receipt of the last passing check of the plan for the Story `key`, if any."""
    try:
        return state.read_json(_receipt_path(repo, key))
    except ValueError:
        return None


def unchecked(repo: Path, scope: str | None) -> str | None:
    """The Story whose plan this work session approved, when no receipt matches that plan as it
    is on disk; None when the session approved no plan or its receipt is current.

    Local files only, so a hook may call it.
    """
    from harness.workflow_evidence import history, option_id

    match work_sessions.select(repo, scope) if scope else None:
        case Ok(session):
            approved = next(
                (
                    entry
                    for entry in reversed(history(session))
                    if entry.get("gate") == "implementation-confirm"
                    and entry.get("status") == "answered"
                    and option_id(entry) == "approve"
                ),
                {},
            )
        case _:
            return None
    match approved.get("artifacts"):
        case [[str() as name, *_]]:
            pass
        case _:
            return None
    match local_artifacts.note((repo / name).resolve()):
        case local_artifacts.Note(work_items=(key,)) as note:
            found = receipt(repo, key) or {}
            return None if found.get("plan_digest") == note.digest else key
        case _:
            return None  # the route's own plan check names a plan that is gone or malformed


def _receipt_path(repo: Path, key: str) -> Path:
    return state.state_dir(repo) / RECEIPTS / f"{state.safe_name(key)}.json"


def _write_receipt(
    repo: Path, key: str, name: str, plan_digest: str, item: WorkItem
) -> Result[None]:
    from harness.workflow_evidence import item_digest

    return attempt(
        lambda: state.write_json(
            _receipt_path(repo, key),
            {
                "story": key,
                "story_digest": item_digest(item),
                "plan": name,
                "plan_digest": plan_digest,
                "checked": datetime.now(UTC).isoformat(),
            },
        ),
        "state_unwritable",
        "plan receipt",
        OSError,
        ValueError,
    )


def _plan_of(repo: Path, key: str) -> Result[str]:
    """The one implementation plan in the artifacts path that names the Story `key`."""
    folder = local_artifacts.artifacts_dir(repo)
    plans = [
        path.resolve().relative_to(repo.resolve()).as_posix()
        for path in (sorted(folder.rglob("*.md")) if folder and folder.is_dir() else ())
        for note in (local_artifacts.note(path),)
        if note is not None
        and artifact_kind(note.kind) == "implementation_plan"
        and key in note.work_items
        and path.resolve().is_relative_to(repo.resolve())
    ]
    match plans:
        case [name]:
            return Ok(name)
        case []:
            return err(
                "plan_invalid",
                f"no implementation plan in the artifacts path names {key}",
            )
        case _:
            return err(
                "plan_invalid",
                f"more than one implementation plan names {key}: {', '.join(plans)}; keep one",
            )


def approved_source(repo: Path, item) -> bool:
    from harness.workflow_evidence import item_digest

    return any(
        note.digest in digests
        and note.kind == "implementation-plan"
        and item.key in note.work_items
        and note.frontmatter.get("source_digest") == item_digest(item)
        for path, digests in local_artifacts.current_pins(repo).items()
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
