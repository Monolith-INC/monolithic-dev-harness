"""Keep a discarded setup review binding after other questions replace the current menu."""

from pathlib import Path

from core.result import Ok, Result, attempt, require
from harness import gates, questions, state

PROPOSAL = Path(".harness/state/setup-proposal.json")
CANCELLED = Path(".harness/state/setup-cancelled.json")


def remember(repo: Path, proposal: dict) -> Result[dict]:
    return attempt(
        lambda: _remember(repo, proposal),
        "setup_unwritable",
        "save setup proposal identity",
        OSError,
    )


def _remember(repo: Path, proposal: dict) -> dict:
    state.ensure_local_exclude(repo)
    state.write_json(repo / PROPOSAL, identity(proposal))
    return proposal


def identity(proposal: dict) -> dict:
    return {key: proposal.get(key) for key in ("digest", "source_digest")}


def binding(repo: Path, gate: str) -> dict | None:
    match gate:
        case "setup-confirm":
            return state.read_json(repo / PROPOSAL)
        case _:
            return None


def cancel(repo: Path, decision: dict) -> Result[object]:
    return attempt(
        lambda: state.write_json(
            repo / CANCELLED,
            {
                "decision_id": decision.get("id"),
                "proposal": decision.get("setup_proposal"),
            },
        ),
        "setup_unwritable",
        "retain discarded setup review",
        OSError,
    )


def check(
    repo: Path, decision: dict, approved_digest: str, source_digest: str
) -> Result[object]:
    match (repo / CANCELLED).exists():
        case False:
            return Ok(None)
        case True:
            return require(
                any(
                    _fresh_confirmation(
                        state.read_json(repo / CANCELLED),
                        entry,
                        {"digest": approved_digest, "source_digest": source_digest},
                    )
                    for entry in (decision, *_after_cancellation(repo))
                ),
                "setup_cancelled",
                "onboarding was cancelled; review and confirm this settings proposal before applying it",
            )


def _after_cancellation(repo: Path) -> tuple[dict, ...]:
    match (
        state.read_json(repo / CANCELLED),
        state.read_json(repo / ".harness/state/decision-history.json"),
    ):
        case {"decision_id": str() as cancelled}, {"answers": list() as entries}:
            return next(
                (
                    tuple(entries[index + 1 :])
                    for index, entry in reversed(tuple(enumerate(entries)))
                    if isinstance(entry, dict)
                    and entry.get("id") == cancelled
                    and entry.get("status") == "cancelled"
                ),
                (),
            )
        case _:
            return ()


def _fresh_confirmation(cancelled: dict | None, decision: dict, proposal: dict) -> bool:
    match cancelled, decision:
        case {"decision_id": str() as old}, {
            "id": str() as current,
            "status": "answered",
            "gate": "setup-confirm",
            "answer": str() as answer,
            "setup_proposal": saved,
        }:
            return current != old and saved == proposal and _accepted(answer)
        case _:
            return False


def _accepted(answer: str) -> bool:
    match gates.load():
        case Ok((_, catalog)) if "setup-confirm" in catalog:
            return any(
                option.id == "yes"
                and questions.choice_label(answer) in option.label.values()
                for option in catalog["setup-confirm"].options
            )
        case _:
            return False
