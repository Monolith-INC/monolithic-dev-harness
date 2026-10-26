"""Scoped decision references and verified publication facts; neither grants permission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from core.result import Err, Ok, Result, bind, err
from harness import decisions, gates, questions, state, work_sessions


def all_history(session: work_sessions.Session) -> tuple[dict, ...]:
    return tuple(
        (state.read_json(session.folder / decisions.HISTORY) or {}).get("answers", ())
    )


def history(session: work_sessions.Session) -> tuple[dict, ...]:
    entries = all_history(session)
    start = next(
        (
            index
            for index, entry in reversed(tuple(enumerate(entries)))
            if entry.get("gate") == "refined-start"
            and entry.get("status") == "answered"
            and option_id(entry) == "rework"
        ),
        0,
    )
    return entries[start:]


def round_id(session: work_sessions.Session) -> str:
    return next(
        (
            entry["id"]
            for entry in reversed(all_history(session))
            if entry.get("gate") == "refined-start"
            and entry.get("status") == "answered"
            and option_id(entry) == "rework"
        ),
        session.id,
    )


def option_id(entry: dict) -> str:
    match gates.load():
        case Ok((_, catalog)):
            return next(
                (
                    option.id
                    for gate in catalog.values()
                    if gate.id == entry.get("gate")
                    for option in gate.options
                    for label in option.label.values()
                    if questions.choice_label(label).casefold()
                    == questions.choice_label(str(entry.get("answer", ""))).casefold()
                ),
                "",
            )
        case _:
            return ""


def latest_approach(session: work_sessions.Session) -> str:
    return next(
        (
            entry["id"]
            for entry in reversed(history(session))
            if entry.get("gate") == "plan-checkpoint"
            and entry.get("status") == "answered"
            and option_id(entry) in {"continue", "stop"}
        ),
        "",
    )


def publications(session: work_sessions.Session) -> tuple[dict, ...]:
    return tuple(
        value
        for path in (session.folder / "publications").glob("*.json")
        for value in (state.read_json(path) or {},)
        if value.get("verified") is True
        and value.get("work_session") == session.id
        and value.get("round") == round_id(session)
    )


def record_publication(repo: Path, item: dict) -> Result[dict]:
    match work_sessions.list_sessions(repo):
        case Ok(sessions):
            match tuple(
                session
                for session in sessions
                if session.status == work_sessions.Status.ACTIVE
                and state.active_approval(repo, session.id) is not None
                and any(
                    entry.get("gate") == "publish-items"
                    and entry.get("status") == "answered"
                    and option_id(entry) == "approve"
                    and questions.approval_id(entry.get("id", ""))
                    == state.active_approval(repo, session.id)[1]["id"]
                    for entry in history(session)
                )
            ):
                case (session,):
                    return Ok(
                        state.write_json(
                            session.folder / "publications" / f"{uuid4().hex}.json",
                            {
                                "verified": True,
                                "work_session": session.id,
                                "round": round_id(session),
                                "item": item["key"],
                                "title": item["title"],
                                "source_digest": item_digest(item),
                                "approach_id": _published_approach(session),
                                "approval_id": state.active_approval(repo, session.id)[
                                    1
                                ]["id"],
                            },
                        )
                    )
                case _:
                    return Ok({})  # Ambiguous owner never becomes a route fact.
        case Err() as failed:
            return failed


def _published_approach(session: work_sessions.Session) -> str:
    entries = history(session)
    latest = latest_approach(session)
    return (
        latest
        if latest
        and any(
            entry.get("gate") == "publish-items" and option_id(entry) == "approve"
            for entry in entries[
                next(
                    index
                    for index, entry in enumerate(entries)
                    if entry.get("id") == latest
                )
                + 1 :
            ]
        )
        else ""
    )


def item_digest(item) -> str:
    from integrations.gateway import plain

    return hashlib.sha256(
        json.dumps(
            {
                key: plain(item).get(key)
                for key in ("key", "title", "description", "kind", "parent_id")
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def gate_ready(
    repo: Path, scope: str | None, gate: str, artifacts: tuple[str, ...] = ()
) -> Result[None]:
    from harness import route, route_facts

    match scope, gate:
        case None, _:
            return Ok(None)
        case _, "planning-methods" | "plan-checkpoint" | "implementation-confirm":
            return bind(
                work_sessions.require_active(repo, scope),
                lambda session: _ready(
                    repo, session, gate, route, route_facts, artifacts
                ),
            )
        case _:
            return Ok(None)


def _ready(repo, session, gate, route, route_facts, artifacts) -> Result[None]:
    facts = route_facts.ProjectFacts(repo, session)
    match gate, facts.answer("planning-depth"):
        case "planning-methods" | "plan-checkpoint", None:
            return err(
                "workflow_prerequisite",
                "Record or explicitly reuse the human planning-depth decision before this gate.",
            )
        case _:
            pass
    match gate:
        case "plan-checkpoint":
            from harness.elicitation_store import hardening_ready

            match hardening_ready(
                repo, session, facts.answer("planning-depth") or "", artifacts
            ):
                case False:
                    return err(
                        "hardening_incomplete",
                        "Complete each selected method's human Apply/Reject decision and preserve the chosen depth's review outputs/triage for this approach before its approval.",
                    )
                case True:
                    pass
        case _:
            pass
    match gate, session.entry_item:
        case "implementation-confirm", str() as key if key:
            match route.load():
                case Ok(loaded):
                    try:
                        found = route.next_step(loaded, facts)
                        return (
                            Ok(None)
                            if found.step and found.step.id == "story-plan"
                            else err(
                                "workflow_prerequisite",
                                f"Complete the next route step ({found.step.id if found.step else 'complete'}) before approving a derived implementation plan.",
                            )
                        )
                    except route_facts.Unreachable as failure:
                        return err("tracker_unreachable", str(failure))
                case Err() as failed:
                    return failed
        case _:
            return Ok(None)


def referenced(repo: Path, session: work_sessions.Session, entry: dict) -> dict:
    match entry:
        case {
            "status": "referenced",
            "source_session": str() as source,
            "source_id": str() as identifier,
        }:
            match work_sessions.select(repo, source):
                case Ok(prior) if (
                    prior.entry_item and prior.entry_item == session.entry_item
                ):
                    return next(
                        (
                            found
                            for found in all_history(prior)
                            if found.get("id") == identifier
                            and found.get("gate") == "planning-depth"
                            and found.get("status") == "answered"
                        ),
                        {},
                    )
                case _:
                    return {}
        case _:
            return entry


def reuse_preference(
    repo: Path, scope: str, source: str, identifier: str
) -> Result[dict]:
    match work_sessions.require_active(repo, scope):
        case Ok(session):
            reference = {
                "id": uuid4().hex,
                "status": "referenced",
                "source_session": source,
                "source_id": identifier,
            }
            match referenced(repo, session, reference):
                case {"gate": "planning-depth"}:
                    state.write_json(
                        session.folder / decisions.HISTORY,
                        {"answers": [*history(session), reference]},
                    )
                    return Ok(reference)
                case _:
                    return err(
                        "invalid_decision_reference",
                        "Only an actual answered planning-depth preference for the same tracked work may be reused; approvals cannot be imported.",
                    )
        case Err() as failed:
            return failed
