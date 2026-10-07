"""Consolidated startup, using the same checked lifecycle as explicit commands."""

from dataclasses import asdict
from pathlib import Path

from core.result import Err, Ok, Result, bind, err, fmap
from harness import (
    decisions,
    discovery,
    onboarding,
    setup,
    startup_receipts,
    work_lifecycle,
    work_sessions,
    workflow,
)


def begin(
    repo: Path, request: str, selected_id: str | None = None, new: bool = False
) -> Result[dict]:
    match onboarding.mode(repo):
        case "free":
            return Ok(onboarding.free_payload(repo, request))
        case _:
            return bind(
                setup.onboarding_status(repo),
                lambda report: _begin_ready(repo, request, selected_id, new, report),
            )


def _begin_ready(
    repo: Path, request: str, selected_id: str | None, new: bool, report: dict
) -> Result[dict]:
    match report:
        case {"status": "ready", "bmad_ready": True}:
            return bind(
                _begin_session(repo, request.strip(), selected_id, new),
                lambda selected: _begin_selected(
                    repo,
                    selected,
                    report,
                    startup_receipts.Invocation(request, selected_id, new),
                ),
            )
        case _:
            return Ok(
                {
                    "state": "setup_needed",
                    "setup": report,
                    "request": request,
                    "next": "Finish bootstrap, then repeat begin with this request.",
                }
            )


def _begin_selected(
    repo: Path,
    selected: work_sessions.Session | dict,
    report: dict,
    invocation: startup_receipts.Invocation,
) -> Result[dict]:
    match selected:
        case dict():
            return Ok(dict(selected))
        case _:
            match decisions.pending(repo, selected.id):
                case pending if pending is None or not decisions.is_blocking(
                    decisions.record(repo, pending.scope) or {}
                ):
                    return bind(
                        _begin_workflow(repo, selected),
                        lambda current: bind(
                            _begin_output(repo, selected, current, report),
                            lambda result: startup_receipts.complete(
                                repo, selected, invocation, result
                            ),
                        ),
                    )
                case pending:
                    return startup_receipts.complete(
                        repo,
                        selected,
                        invocation,
                        {
                            "state": "waiting_for_human",
                            "session_id": selected.id,
                            "request": selected.request,
                            "language": report["language"],
                            **asdict(pending),
                            "next": "Re-present the saved question with harness decision fallback; do not advance until answered.",
                        },
                    )


def _begin_workflow(
    repo: Path, selected: work_sessions.Session
) -> Result[workflow.Workflow]:
    match workflow.load(repo, selected.id):
        case Ok() as current:
            return current
        case Err(failure) if failure.code == "workflow_absent":
            return bind(
                work_lifecycle.start_workflow(repo, selected.request, selected.id),
                lambda fresh: fmap(
                    workflow.save(repo, fresh, selected.id), lambda _: fresh
                ),
            )
        case Err() as failure:
            return failure


def _begin_output(
    repo: Path,
    selected: work_sessions.Session,
    current: workflow.Workflow,
    report: dict,
) -> Result[dict]:
    match (current.status, current.current.stage):
        case ["active", "discover"]:
            return fmap(
                discovery.render(repo, selected.id),
                lambda package: _begin_payload(
                    selected, current, report, package["entry"]
                ),
            )
        case _:
            return Ok(_begin_payload(selected, current, report, ""))


def _begin_payload(
    selected: work_sessions.Session,
    current: workflow.Workflow,
    report: dict,
    entry: str,
) -> dict:
    return {
        "state": current.status,
        "session_id": selected.id,
        "request": selected.request,
        "language": report["language"],
        "workflow": {
            "stage": current.current.stage,
            "checkpoint": current.current.label,
            "next_action": current.current.next_action,
            "saved_points": len(current.points),
        },
        "discover_entry": entry,
        "next": "Follow saved next_action; for fresh discovery read discover_entry. Paused work requires explicit resume.",
    }


def _begin_session(
    repo: Path, request: str, selected_id: str | None, new: bool
) -> Result[work_sessions.Session | dict]:
    match (selected_id, new):
        case str() as chosen, False:
            return work_lifecycle.choose(repo, chosen)
        case None, True:
            return work_sessions.create(repo, request)
        case None, False:
            return bind(
                work_sessions.route(repo, request),
                lambda routed: _begin_route(repo, request, routed),
            )
        case _:
            return err("invalid_session", "choose --session or --new, not both")


def _begin_route(
    repo: Path, request: str, routed: dict
) -> Result[work_sessions.Session | dict]:
    match routed["action"]:
        case "continue_active":
            return work_lifecycle.choose(repo, routed["session_id"])
        case "start_new":
            return work_sessions.create(repo, request)
        case _:
            return Ok(
                {
                    "state": "choose_session",
                    "candidates": routed["candidates"],
                    "next": "Offer saved sessions and Start new; repeat begin with --session or --new after the choice.",
                }
            )
