"""Checked work lifecycle operations shared by startup and explicit CLI commands."""

from pathlib import Path

from core.result import Err, Failure, Ok, Result, bind, fmap, require
from harness import discovery, preferences, work_sessions, workflow


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
            lambda language: bind(
                require(
                    bool(language),
                    "language_unset",
                    "choose English or Português (Brasil) before starting",
                ),
                lambda _: workflow.start(request, language),
            ),
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
