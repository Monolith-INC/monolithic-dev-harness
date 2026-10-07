"""A pending decision owns an idempotent projection into its workflow review history.

The decision file is written first. Its recovery metadata survives projection or cleanup failure;
no workflow checkpoint is created for a decision that failed validation or persistence.
"""

from dataclasses import asdict
from pathlib import Path

from core.result import Err, Ok, Result, attempt, bind, err, fmap, require
from harness import decisions, state, work_sessions, workflow

RECOVERY = "review_checkpoint"


def begin(
    repo: Path,
    key: str,
    question: str,
    options: tuple[str, ...],
    transport: str,
    artifacts: tuple[tuple[str, str], ...] = (),
    approval: bool = False,
    *,
    work_session_id: str | None = None,
    allow_free_text: bool = False,
    details: tuple[str, ...] = (),
    gate: str = "",
    binds: dict | None = None,
) -> Result[dict]:
    return bind(
        _checkpoint(repo, work_session_id, question, artifacts),
        lambda checkpoint: bind(
            decisions.begin(
                repo,
                key,
                question,
                options,
                transport,
                artifacts,
                approval,
                review_checkpoint=checkpoint,
                work_session_id=work_session_id,
                allow_free_text=allow_free_text,
                details=details,
                gate=gate,
                binds=binds,
            ),
            lambda value: fmap(
                recover(repo, work_session_id),
                lambda _: {key: item for key, item in value.items() if key != RECOVERY},
            ),
        ),
    )


def _checkpoint(
    repo: Path, scope: str | None, question: str, artifacts: tuple[tuple[str, str], ...]
) -> Result[dict | None]:
    match artifacts:
        case ():
            return Ok(None)
        case _:
            match workflow.load(repo, scope):
                case Err(failure) if failure.code == "workflow_absent":
                    return Ok(None)
                case Err() as failure:
                    return failure
                case Ok(current) if current.status != "active":
                    return Ok(None)
                case Ok(current):
                    return fmap(
                        workflow.add_point(
                            current,
                            question,
                            current.current.stage,
                            artifacts=artifacts,
                            pending=question,
                            next_action="Continue from the human's answer to: "
                            + question,
                        ),
                        lambda updated: {
                            "before": asdict(current),
                            "after": asdict(updated),
                        },
                    )


def recover(repo: Path, scope: str | None = None) -> Result[object]:
    return bind(
        work_sessions.scope_folder(repo, scope),
        lambda folder: _recover_at(repo, folder),
    )


def _recover_at(repo: Path, folder: Path) -> Result[object]:
    match state.read_json(folder / "decision.json"):
        case {"review_checkpoint": recovery} as decision:
            return bind(
                _validated(decision, recovery),
                lambda versions: bind(
                    workflow.read_file(folder / "workflow.json"),
                    lambda current: bind(
                        _project(repo, folder, current, *versions),
                        lambda _: _clear(folder, decision),
                    ),
                ),
            )
        case _:
            return Ok(None)


def _validated(
    decision: dict, recovery: object
) -> Result[tuple[workflow.Workflow, workflow.Workflow]]:
    match recovery:
        case {"before": before, "after": after}:
            return bind(
                workflow.from_dict(before),
                lambda previous: bind(
                    workflow.from_dict(after),
                    lambda intended: fmap(
                        require(
                            decision.get("status") in ("pending", "answered")
                            and intended.current.pending == decision.get("question")
                            and [list(pair) for pair in intended.current.artifacts]
                            == decision.get("artifacts", [])
                            and workflow.add_point(
                                previous,
                                intended.current.label,
                                previous.current.stage,
                                artifacts=intended.current.artifacts,
                                pending=intended.current.pending,
                                next_action=intended.current.next_action,
                            )
                            == Ok(intended),
                            "review_recovery_invalid",
                            "saved review recovery does not match its decision",
                        ),
                        lambda _: (previous, intended),
                    ),
                ),
            )
        case _:
            return err("review_recovery_invalid", "saved review recovery is malformed")


def _project(
    repo: Path,
    folder: Path,
    current: workflow.Workflow,
    before: workflow.Workflow,
    after: workflow.Workflow,
) -> Result[object]:
    match current:
        case _ if current == after:
            return Ok(None)
        case _ if current == before:
            return workflow.persist(repo, after, folder / "workflow.json")
        case _:
            return err(
                "review_recovery_conflict",
                "workflow changed during review recovery; preserve it and inspect before continuing",
            )


def _clear(folder: Path, expected: dict) -> Result[object]:
    return bind(
        require(
            state.read_json(folder / "decision.json") == expected,
            "review_recovery_conflict",
            "decision changed during review recovery; retry from its current record",
        ),
        lambda _: attempt(
            lambda: state.write_json(
                folder / "decision.json",
                {key: value for key, value in expected.items() if key != RECOVERY},
            ),
            "review_recovery_unwritable",
            "complete review recovery",
            OSError,
        ),
    )
