"""Checked work lifecycle operations shared by startup and explicit CLI commands."""

from pathlib import Path

from core.result import Err, Failure, Ok, Result, bind, err, fmap, require
from harness import (
    code_content,
    discovery,
    preferences,
    settings,
    work_sessions,
    workflow,
)
from integrations import registry
from integrations.contracts import ENTRY_KINDS, TrackerOps, WorkItem


def resume(
    repo: Path, identifier: str, *, make_current: bool = True
) -> Result[work_sessions.Session]:
    return bind(
        discovery.onboarding_ready(repo),
        lambda _: bind(
            discovery.verify(repo, identifier),
            lambda _: work_sessions.transition(
                repo, identifier, "resume", make_current=make_current
            ),
        ),
    )


def choose(repo: Path, identifier: str) -> Result[work_sessions.Session]:
    return bind(
        work_sessions.select(repo, identifier), lambda selected: _choose(repo, selected)
    )


def _choose(
    repo: Path, selected: work_sessions.Session
) -> Result[work_sessions.Session]:
    match selected.status:
        case work_sessions.Status.ACTIVE:
            return fmap(discovery.verify(repo, selected.id), lambda _: selected)
        case work_sessions.Status.PAUSED | work_sessions.Status.STOPPED:
            return resume(repo, selected.id, make_current=False)
        case _:
            return Ok(selected)


def start_workflow(
    repo: Path, request: str, session_id: str | None = None
) -> Result[workflow.Workflow]:
    def begin(_: object) -> Result[workflow.Workflow]:
        return bind(
            bind(
                discovery.onboarding_ready(repo),
                lambda _: preferences.language_for(repo),
            ),
            lambda language: workflow.start(request, language),
        )

    match workflow.load(repo, session_id):
        case Ok(current) if current.status in workflow.TERMINAL_STATUSES:
            return bind(workflow.archive_terminal(repo, session_id), begin)
        case Ok():
            return Err(Failure("workflow_exists", "a workflow is already saved"))
        case Err(failure) if failure.code == "workflow_absent":
            match session_id:
                case None:
                    return begin(None)
                case _:
                    pass
            return bind(
                work_sessions.select(repo, session_id),
                lambda session: bind(
                    require(
                        not request or request.strip() == session.request,
                        "invalid_workflow",
                        "the workflow request must match its work session",
                    ),
                    begin,
                ),
            )
        case Err() as failure:
            return failure


def track(
    repo: Path, session_id: str, entry_item: str
) -> Result[work_sessions.Session]:
    """Record the Epic, Feature, Story or Bug the user started from, once it is in the tracker."""
    return bind(
        _ops(repo),
        lambda ops: bind(
            ops.get_work_item(entry_item.strip()),
            lambda item: (
                work_sessions.track(repo, session_id, item.key)
                if item.kind in ENTRY_KINDS
                else err(
                    "invalid_request",
                    f"{item.key} is a {item.kind.value}; work starts from an Epic, Feature, "
                    "Story or Bug",
                )
            ),
        ),
    )


def link(repo: Path, session_id: str, work_item: str) -> Result[work_sessions.Session]:
    """Link the work session to its Story or Bug, which must sit under the item it tracks; each
    work item's first link records the code as it is."""
    return bind(
        work_sessions.require_active(repo, session_id),
        lambda session: bind(
            _under_entry(repo, session.entry_item, work_item.strip()),
            lambda _: bind(
                work_sessions.save_link(session, work_item),
                lambda linked: fmap(
                    _record_baseline(repo, linked.work_item), lambda _: linked
                ),
            ),
        ),
    )


def _ops(repo: Path) -> Result[TrackerOps]:
    return registry.open_selected(repo, settings.load(repo))


def _under_entry(repo: Path, entry: str, key: str) -> Result[None]:
    """`key` is the entry item or one of its descendants, following parents in the tracker."""
    if not entry or key.casefold() == entry.casefold():
        return Ok(None)
    outside = err(
        "invalid_request",
        f"{key} is not under {entry}, the item this work session tracks; start a new work "
        "session for it",
    )

    def climb(
        ops: TrackerOps, top: WorkItem, ref: str, seen: frozenset[str]
    ) -> Result[None]:
        def step(item: WorkItem) -> Result[None]:
            match item:
                case _ if item.is_child_of(top):
                    return Ok(None)
                case WorkItem(parent_id=parent) if parent and (
                    parent.casefold() not in seen
                ):
                    return climb(ops, top, parent, seen | {ref.casefold()})
                case _:
                    return outside

        return bind(ops.get_work_item(ref), step)

    return bind(
        _ops(repo),
        lambda ops: bind(
            ops.get_work_item(entry), lambda top: climb(ops, top, key, frozenset())
        ),
    )


def _record_baseline(repo: Path, work_item: str) -> Result[None]:
    try:
        code_content.record_baseline(repo, work_item)
    except OSError as exc:
        return Err(
            Failure("session_unwritable", f"could not record the code baseline: {exc}")
        )
    return Ok(None)
