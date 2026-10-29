"""Protected chooser persistence and source-result evidence; domain transitions are pure."""

from __future__ import annotations

import csv
import fcntl
import random
from dataclasses import asdict, replace
from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, fmap
from harness import state, work_sessions, workflow
from harness.elicitation import SelectionEvent, SelectionState, reduce_selection


def _path(repo: Path, scope: str) -> Path:
    from harness.workflow_evidence import round_id

    match work_sessions.select(repo, scope):
        case Ok(session):
            return (
                session.folder
                / "planning"
                / state.safe_name(round_id(session))
                / "elicitation.json"
            )
        case _:
            return (
                work_sessions.root(repo)
                / state.safe_name(scope)
                / "planning/invalid/elicitation.json"
            )


def load(repo: Path, scope: str) -> Result[SelectionState]:
    match scope:
        case "":
            return err(
                "elicitation_absent",
                "Choose the owning work session before selecting methods.",
            )
        case _:
            pass
    match state.read_json(_path(repo, scope)):
        case {"selection": dict() as saved}:
            return attempt(
                lambda: SelectionState(
                    **{
                        **saved,
                        "selected": tuple(saved["selected"]),
                        "pool": tuple(saved["pool"]),
                        "outcomes": tuple(tuple(item) for item in saved["outcomes"]),
                        "events": tuple(saved["events"]),
                        "directions": tuple(saved.get("directions", ())),
                    }
                ),
                "invalid_elicitation_state",
                "Method selection cannot be read; preserve it and recover the session.",
                KeyError,
                TypeError,
            )
        case _:
            return err(
                "elicitation_absent",
                "Start the source chooser with harness elicitation start, then present its choices.",
            )


def save(repo: Path, scope: str, current: SelectionState) -> Result[SelectionState]:
    return bind(
        work_sessions.require_active(repo, scope),
        lambda _: fmap(
            attempt(
                lambda: state.write_json(
                    _path(repo, scope),
                    {
                        **(state.read_json(_path(repo, scope)) or {}),
                        "selection": asdict(current),
                    },
                ),
                "elicitation_unwritable",
                "Could not save method selection",
                OSError,
            ),
            lambda _: current,
        ),
    )


def catalog() -> dict[str, str]:
    with (
        Path(__file__).resolve().parents[2]
        / "skills/bmad-advanced-elicitation/assets/methods.csv"
    ).open() as source:
        return {entry["num"]: entry["method_name"] for entry in csv.DictReader(source)}


def stage(
    repo,
    scope,
    question: str,
    choices: dict[str, dict],
    artifact: str = "",
    digest: str = "",
) -> Result[dict]:
    from harness import decisions

    match decisions.pending(repo, scope):
        case decisions.Pending():
            return err(
                "decision_pending",
                "Preserve the pending choice; use harness decision fallback rather than replace its chooser state.",
            )
        case None:
            pass
    pending = {
        "question": question,
        "options": tuple(choices),
        "choices": choices,
        "artifact": artifact,
        "digest": digest,
    }
    state.write_json(
        _path(repo, scope),
        {**(state.read_json(_path(repo, scope)) or {}), "pending": pending},
    )
    return Ok(pending)


def stage_result(repo: Path, scope: str, artifact: str) -> Result[dict]:
    return bind(
        load(repo, scope),
        lambda current: bind(
            _artifact(repo, artifact),
            lambda digest: (
                stage(
                    repo,
                    scope,
                    f"Apply findings from {catalog().get(current.selected[len(current.outcomes)], current.selected[len(current.outcomes)])}?",
                    {
                        "Apply": {"action": "apply"},
                        "Reject": {"action": "reject"},
                        "Give direction": {"action": "direction"},
                    },
                    artifact,
                    digest,
                )
                if current.phase == "apply"
                and len(current.outcomes) < len(current.selected)
                else err(
                    "elicitation_phase",
                    "Finish selecting methods before proposing the next method's findings.",
                )
            ),
        ),
    )


def _artifact(repo: Path, name: str) -> Result[str]:
    match (
        bool(name)
        and not Path(name).is_absolute()
        and (repo / name).resolve().is_relative_to(repo.resolve())
    ):
        case True:
            return workflow.file_digest(repo / name)
        case False:
            return err(
                "invalid_elicitation_artifact",
                "Name an existing file inside this project",
            )


def binding(
    repo: Path, scope: str | None, question: str, options: tuple[str, ...]
) -> dict:
    match scope:
        case None | "":
            return {}
        case _:
            pass
    match state.read_json(_path(repo, scope or "")), load(repo, scope or ""):
        case {"pending": {"question": str() as text, "options": list() as labels}}, Ok(
            current
        ) if text == question and tuple(labels) == options:
            return {"revision": current.revision}
        case _:
            return {}


def capture(repo: Path, scope: str, decision: dict) -> Result[SelectionState]:
    match scope:
        case "":
            return err("elicitation_absent", "A work session is required")
        case _:
            with (_path(repo, scope).parent / "elicitation.lock").open("a+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                return bind(
                    load(repo, scope),
                    lambda current: _capture(repo, scope, current, decision),
                )


def _capture(repo, scope, current, decision) -> Result[SelectionState]:
    match decision.get("id") in current.events:
        case True:
            return Ok(current)
        case False:
            pass
    pending = (state.read_json(_path(repo, scope)) or {}).get("pending", {})
    match decision, pending:
        case {
            "id": str() as identifier,
            "status": "answered",
            "elicitation": {"revision": int() as revision},
            "answer": str() as answer,
            "question": str() as text,
        }, {
            "question": str() as question,
            "choices": dict() as choices,
            "artifact": str() as artifact,
            "digest": str() as digest,
        } if revision == current.revision and text == question and answer in choices:
            match bool(artifact) and workflow.file_digest(repo / artifact) != Ok(
                digest
            ):
                case True:
                    return err(
                        "elicitation_artifact_changed",
                        "The displayed method result changed; show it and ask again.",
                    )
                case False:
                    return bind(
                        reduce_selection(
                            current,
                            SelectionEvent(
                                **{
                                    **choices[answer],
                                    **(
                                        {
                                            "methods": tuple(
                                                random.SystemRandom().sample(
                                                    tuple(catalog()),
                                                    min(5, len(catalog())),
                                                )
                                            )
                                        }
                                        if choices[answer]["action"] == "reshuffle"
                                        else {}
                                    ),
                                },
                                artifact=artifact,
                                digest=digest,
                            ),
                        ),
                        lambda updated: save(
                            repo,
                            scope,
                            replace(updated, events=(*updated.events, identifier)),
                        ),
                    )
        case {
            "id": str() as identifier,
            "status": "answered",
            "elicitation": {"revision": int() as revision},
            "answer": str() as answer,
            "question": str() as text,
        }, {"question": str() as question} if (
            revision == current.revision and text == question
        ):
            named = {name.casefold(): key for key, name in catalog().items()} | {
                key: key for key in catalog()
            }
            methods = tuple(
                named.get(part.strip().casefold(), "") for part in answer.split(",")
            )
            return bind(
                reduce_selection(
                    current,
                    SelectionEvent("add", methods)
                    if current.phase == "choose" and all(methods)
                    else SelectionEvent("direction"),
                ),
                lambda updated: save(
                    repo,
                    scope,
                    replace(
                        updated,
                        events=(*updated.events, identifier),
                        directions=(*updated.directions, answer),
                    ),
                ),
            )
        case _:
            return err(
                "elicitation_reply_mismatch",
                "Only the matching captured human selection can advance this method result.",
            )


def present_selection(repo, scope) -> Result[dict]:
    return bind(
        load(repo, scope), lambda current: _selection_question(repo, scope, current)
    )


def _selection_question(repo, scope, current) -> Result[dict]:
    match current.phase, current.mode:
        case "choose", "recommendations":
            return stage(
                repo,
                scope,
                "Use the proposed method selection?",
                {
                    "Use proposed set": {
                        "action": "accept_set",
                        "methods": current.pool,
                    },
                    "Choose individually": {"action": "individual"},
                    "Show full catalog": {"action": "catalog"},
                },
            )
        case "choose", "actions":
            return stage(
                repo,
                scope,
                "How would you like to continue selecting methods?",
                {
                    "Reshuffle": {"action": "reshuffle"},
                    "Show full catalog": {"action": "catalog"},
                    "Proceed": {"action": "finish"},
                },
            )
        case "choose", _:
            available = tuple(
                method
                for method in (
                    tuple(catalog()) if current.mode == "catalog" else current.pool
                )
                if method not in current.selected
            )
            offered = tuple(
                available[
                    (current.page * (1 if current.selected else 2))
                    % max(len(available), 1) :
                ][: 1 if current.selected or current.mode == "catalog" else 2]
            )
            return stage(
                repo,
                scope,
                "Which method would you like to add?",
                {
                    **{
                        catalog()[method]: {"action": "add", "methods": (method,)}
                        for method in offered
                    },
                    **(
                        {"Next page": {"action": "next"}}
                        if current.mode == "catalog"
                        else {"More choices": {"action": "more"}}
                    ),
                    **(
                        {"Finish selection": {"action": "finish"}}
                        if current.selected
                        else {}
                    ),
                },
            )
        case _:
            return err(
                "elicitation_phase",
                f"Saved phase is {current.phase}; propose the next result or record hardening evidence.",
            )


def record_hardening(
    repo, scope, kind: str, artifact: str, triage: str, approach: str
) -> Result[dict]:
    return bind(
        _artifact(repo, artifact),
        lambda digest: bind(
            _artifact(repo, triage),
            lambda triage_digest: bind(
                _artifact(repo, approach),
                lambda approach_digest: _save_review(
                    repo,
                    scope,
                    kind,
                    artifact,
                    digest,
                    triage,
                    triage_digest,
                    approach,
                    approach_digest,
                ),
            ),
        ),
    )


def _save_review(
    repo,
    scope,
    kind,
    artifact,
    digest,
    triage,
    triage_digest,
    approach,
    approach_digest,
):
    return bind(
        work_sessions.require_active(repo, scope),
        lambda _: _review_written(
            repo,
            scope,
            kind,
            artifact,
            digest,
            triage,
            triage_digest,
            approach,
            approach_digest,
        ),
    )


def _review_written(
    repo,
    scope,
    kind,
    artifact,
    digest,
    triage,
    triage_digest,
    approach,
    approach_digest,
):
    saved = state.read_json(_path(repo, scope)) or {}
    entry = {
        "kind": kind,
        "artifact": artifact,
        "digest": digest,
        "triage": triage,
        "triage_digest": triage_digest,
        "approach": approach,
        "approach_digest": approach_digest,
    }
    state.write_json(
        _path(repo, scope), {**saved, "reviews": [*saved.get("reviews", ()), entry]}
    )
    return Ok(entry)


def methods_complete(repo, scope) -> bool:
    match load(repo, scope):
        case Ok(current) if current.phase == "hardening":
            return all(
                workflow.file_digest(repo / artifact) == Ok(digest)
                for _, _, artifact, digest in current.outcomes
            )
        case _:
            return False


def methods_selected(repo, scope) -> bool:
    match load(repo, scope):
        case Ok(current):
            return bool(current.selected) and current.phase in {"apply", "hardening"}
        case _:
            return False


def hardening_ready(
    repo, session, depth: str, approaches: tuple[str, ...] = ()
) -> bool:
    return not hardening_gaps(repo, session, depth, approaches)


def hardening_gaps(
    repo, session, depth: str, approaches: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """What still keeps this approach from its approval: unapplied methods, and each required
    review that is missing, recorded for another approach, or changed since it was recorded."""
    required = (
        ("readiness",)
        + (
            ("risks", "edge_cases", "input_reconciliation", "technical_choices")
            if depth != "light"
            else ()
        )
        + (
            ("adversarial", "assumptions", "source_preservation", "verification_gap")
            if depth == "hardcore"
            else ()
        )
    )
    reviews = tuple((state.read_json(_path(repo, session.id)) or {}).get("reviews", ()))

    def current(review: dict) -> bool:
        return (
            _artifact(repo, review.get("artifact", "")) == Ok(review.get("digest"))
            and _artifact(repo, review.get("triage", ""))
            == Ok(review.get("triage_digest"))
            and _artifact(repo, review.get("approach", ""))
            == Ok(review.get("approach_digest"))
        )

    def gap(kind: str) -> str | None:
        mine = [r for r in reviews if r.get("kind") == kind]
        here = [r for r in mine if r.get("approach") in approaches]
        if any(current(r) for r in here):
            return None
        if here:
            return f"{kind} review changed since it was recorded"
        if mine:
            recorded = ", ".join(sorted({str(r.get("approach")) for r in mine}))
            return f"{kind} review is recorded for {recorded}, not {', '.join(approaches) or 'no --artifact'}"
        return f"{kind} review missing"

    return tuple(
        (
            ()
            if depth == "light" or methods_complete(repo, session.id)
            else ("selected methods still need their Apply/Reject decisions",)
        )
        + tuple(found for kind in required if (found := gap(kind)))
    )
