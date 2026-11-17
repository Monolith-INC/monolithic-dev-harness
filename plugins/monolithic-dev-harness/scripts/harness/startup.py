"""Consolidated startup, using the same checked lifecycle as explicit commands."""

import shlex
from dataclasses import asdict
from pathlib import Path

from core.result import Err, Ok, Result, bind, err, fmap
from harness import (
    decisions,
    discovery,
    onboarding,
    route_facts,
    session_entry,
    setup,
    startup_receipts,
    work_lifecycle,
    work_sessions,
    workflow,
)


def begin(
    repo: Path,
    request: str,
    selected_id: str | None = None,
    new: bool = False,
    host: str = "",
    conversation: str = "",
) -> Result[dict]:
    match onboarding.mode(repo):
        case "free":
            return Ok(onboarding.free_payload(repo, request))
        case _:
            return _begin_entry(repo, request, selected_id, new, host, conversation)


def _begin_entry(
    repo: Path,
    request: str,
    selected_id: str | None,
    new: bool,
    host: str,
    conversation: str,
) -> Result[dict]:
    from host_adapters import startup_context, work_session_context

    match bool(conversation):
        case False:
            match startup_context.identity_for_invocation(
                repo,
                startup_receipts.Invocation(request, selected_id, new),
                host,
            ):
                case Err() as failure:
                    return failure
                case Ok((resolved_host, resolved_conversation)):
                    host, conversation = resolved_host, resolved_conversation
                case _:
                    pass
        case _:
            pass

    match (host, conversation):
        case ("codex" | "claude" | "cursor", str() as identity) if identity:
            match session_entry.recover_reply(repo, host, identity):
                case Err() as failure:
                    return failure
                case Ok(str() as _choice):
                    match session_entry.apply_selection(repo, host, identity):
                        case Err() as failure:
                            return failure
                        case Ok():
                            pass
                case _:
                    pass
            match session_entry.selected(repo, host, identity):
                case "setup":
                    return _begin_setup_handover(repo, request)
                case str() as selected if selected.startswith("WS-"):
                    return _begin_unpaused(
                        repo,
                        request,
                        selected,
                        False,
                        startup_receipts.Invocation(request, selected_id, new),
                    )
                case _:
                    match work_session_context.resolve_session(repo, host, identity):
                        case Ok(str()):
                            return _begin_unpaused(repo, request, selected_id, new)
                        case Ok(None):
                            return _offer_entry(
                                repo, request, selected_id, new, host, identity
                            )
                        case Err() as failure:
                            return failure
        case _:
            found = session_entry.candidates(repo, conversation)
            match bool(found.sessions or found.unfinished_setup):
                case False:
                    pass
                case True:
                    return err(
                        "entry_identity_missing",
                        "Saved work or unfinished setup is available, but this conversation has no trusted identity for a human choice.",
                    )
            if selected_id is not None or new:
                return err(
                    "entry_identity_missing",
                    "This conversation has no trusted identity for a saved-work choice.",
                )
            return _begin_unpaused(repo, request, selected_id, new)


def _offer_entry(
    repo: Path,
    request: str,
    selected_id: str | None,
    new: bool,
    host: str,
    conversation: str,
) -> Result[dict]:
    found = session_entry.candidates(repo, conversation)
    match bool(found.sessions or found.unfinished_setup):
        case False:
            return _begin_unpaused(repo, request, selected_id, new)
        case True if selected_id is not None or new:
            return err(
                "entry_choice_required",
                "Choose saved work or unfinished setup through the conversation's session-entry question first.",
            )
        case True:
            return bind(
                session_entry.offer(repo, host, conversation, request),
                lambda prepared: Ok(
                    {
                        "state": "choose_session",
                        "request": prepared.request,
                        "candidates": [
                            {"id": item.id, "request": item.request}
                            for item in found.sessions[:3]
                        ],
                        "unfinished_setup": found.unfinished_setup,
                        "command": (
                            "harness decision present --gate session-entry "
                            f"--host {host} --entry-request {shlex.quote(prepared.request)} "
                            f"--repo {shlex.quote(str(repo))}"
                        ),
                        "next": "Show this question and wait for the human's answer before continuing.",
                    }
                ),
            )


def _begin_unpaused(
    repo: Path,
    request: str,
    selected_id: str | None,
    new: bool,
    invocation: startup_receipts.Invocation | None = None,
) -> Result[dict]:
    match onboarding.status(repo):
        case {"status": "paused"}:
            return Ok(
                {
                    "state": "paused",
                    "request": request,
                    "next": "Resume, reset or drop onboarding when the user chooses; preserve existing progress.",
                }
            )
        case _:
            return bind(
                setup.onboarding_status(repo),
                lambda report: _begin_ready(
                    repo, request, selected_id, new, report, invocation
                ),
            )


def _begin_ready(
    repo: Path,
    request: str,
    selected_id: str | None,
    new: bool,
    report: dict,
    invocation: startup_receipts.Invocation | None = None,
) -> Result[dict]:
    match report:
        case {"status": "ready", "bmad_ready": True}:
            return bind(
                _begin_session(repo, request.strip(), selected_id, new),
                lambda selected: _begin_selected(
                    repo,
                    selected,
                    report,
                    invocation
                    or startup_receipts.Invocation(request, selected_id, new),
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


def _begin_setup_handover(repo: Path, request: str) -> Result[dict]:
    from dataclasses import asdict as to_dict

    match decisions.pending(repo):
        case decisions.Pending() as pending:
            return Ok(
                {
                    "state": "waiting_for_human",
                    "request": request,
                    **to_dict(pending),
                    "next": "Re-present the saved setup question through `harness decision fallback` and wait for the answer.",
                }
            )
        case _:
            return _begin_unpaused(repo, request, None, False)


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


# Steps before refinement run inside bmad-build's rendered instructions.
_DISCOVERY_STAGES = frozenset({"discovery", "planning", "hardening"})


def _begin_output(
    repo: Path,
    selected: work_sessions.Session,
    current: workflow.Workflow,
    report: dict,
) -> Result[dict]:
    if current.status != "active":
        return Ok(_begin_payload(selected, current, report, "", {}))
    match route_facts.next_for(repo, selected.id):
        case Ok(found):
            step = found
        case Err(failure):
            step = {"state": failure.code, "say": failure.message}
    if step.get("stage") in _DISCOVERY_STAGES:
        return fmap(
            discovery.render(repo, selected.id),
            lambda package: _begin_payload(
                selected, current, report, package["entry"], step
            ),
        )
    return Ok(_begin_payload(selected, current, report, "", step))


def _begin_payload(
    selected: work_sessions.Session,
    current: workflow.Workflow,
    report: dict,
    entry: str,
    step: dict,
) -> dict:
    return {
        "state": current.status,
        "session_id": selected.id,
        "request": selected.request,
        "language": report["language"],
        "next": step,
        "discover_entry": entry,
        "instruction": "Do the step in `next`, then run `harness next` and do the step it "
        "gives, until it says the work is complete. When `discover_entry` is set, the "
        "step's skill starts there. Paused work requires an explicit resume.",
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
