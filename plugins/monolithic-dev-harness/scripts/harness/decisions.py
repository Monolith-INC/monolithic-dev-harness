"""A durable pending human decision; only trusted prompt/answer hooks resolve it."""

from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, fmap
from harness import policies, state

RELATIVE_PATH = Path(".harness/state/decision.json")


def _path(
    repo: Path, work_session_id: str | None, *, active: bool = False
) -> Result[Path]:
    if work_session_id is None:
        return Ok(repo / RELATIVE_PATH)
    from harness import work_sessions

    selected = (
        work_sessions.require_active(repo, work_session_id)
        if active
        else work_sessions.select(repo, work_session_id)
    )
    return fmap(selected, lambda session: session.folder / "decision.json")


def record(repo: Path, work_session_id: str | None = None) -> dict[str, Any] | None:
    match _path(repo, work_session_id):
        case Ok(path):
            return state.read_json(path)
        case Err():
            return None


def waiting(repo: Path, work_session_id: str | None = None) -> bool:
    global_pending = _waiting_at(repo / RELATIVE_PATH)
    if work_session_id is None:
        return global_pending
    match _path(repo, work_session_id):
        case Ok(path):
            return global_pending or _waiting_at(path)
        case Err():
            return True


def _waiting_at(path: Path) -> bool:
    return path.exists() and (state.read_json(path) or {}).get("status") != "answered"


def any_waiting(repo: Path) -> bool:
    if _waiting_at(repo / RELATIVE_PATH):
        return True
    from harness import work_sessions

    match work_sessions.list_sessions(repo):
        case Ok(sessions):
            return any(
                _waiting_at(session.folder / "decision.json") for session in sessions
            )
        case Err():
            return True


def pending_for(
    repo: Path, work_session_id: str | None = None
) -> dict[str, Any] | None:
    pending, _scope = pending_scope(repo, work_session_id)
    return pending


def pending_scope(
    repo: Path, work_session_id: str | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Return the pending decision and the storage scope it actually belongs to."""
    scoped = record(repo, work_session_id)
    if scoped and scoped.get("status") == "pending":
        return scoped, work_session_id
    global_record = record(repo)
    if global_record and global_record.get("status") == "pending":
        return global_record, None
    return None, work_session_id


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
) -> Result[dict[str, Any]]:
    return bind(
        _path(repo, work_session_id, active=True),
        lambda path: attempt(
            lambda: _begin(
                path,
                repo,
                key,
                question,
                options,
                transport,
                artifacts,
                approval,
                work_session_id,
            ),
            "decision_invalid",
            "human decision",
            OSError,
            ValueError,
        ),
    )


def _begin(
    path: Path,
    repo: Path,
    key: str,
    question: str,
    options: tuple[str, ...],
    transport: str,
    artifacts: tuple[tuple[str, str], ...],
    approval: bool,
    work_session_id: str | None,
) -> dict[str, Any]:
    if waiting(repo, work_session_id):
        raise ValueError("answer the pending question before asking another")
    if (
        not key
        or not question.strip()
        or not options
        or len(options) > 3
        or any(not option.strip() for option in options)
        or len({option.strip().casefold() for option in options}) != len(options)
        or transport not in ("chat", "blocking", "async")
    ):
        raise ValueError("a decision needs an id, question, and distinct options")
    value = {
        "id": key,
        "question": question,
        "options": options,
        "transport": transport,
        "artifacts": artifacts,
        "approval": approval,
        "status": "pending",
        "answer": "",
    }
    if work_session_id:
        value["work_session_id"] = work_session_id
    state.write_json(path, value)
    return value


def resolve(
    repo: Path,
    key: str,
    answer: str,
    source: str,
    *,
    work_session_id: str | None = None,
) -> Result[dict[str, Any]]:
    return bind(
        _path(repo, work_session_id),
        lambda path: attempt(
            lambda: _resolve(repo, path, key, answer, source),
            "decision_invalid",
            "human answer",
            OSError,
            ValueError,
        ),
    )


def bind_question(
    repo: Path,
    presentation_id: str,
    tool_id: str,
    question: str,
    options: tuple[str, ...],
    *,
    work_session_id: str | None = None,
) -> Result[dict[str, Any]]:
    match _path(repo, work_session_id):
        case Err() as failure:
            return failure
        case Ok(path):
            pass

    def bind_native() -> dict[str, Any]:
        current = state.read_json(path) or {}
        if (
            not tool_id
            or current.get("status") != "pending"
            or current.get("transport") not in ("blocking", "async")
            or current.get("id") != presentation_id
            or current.get("question") != question
            or tuple(current.get("options", ())) != options
            or current.get("presentation_id")
        ):
            raise ValueError("this question does not match the prepared decision")
        updated = {**current, "presentation_id": presentation_id, "id": tool_id}
        state.write_json(path, updated)
        return updated

    return attempt(
        bind_native, "decision_invalid", "native question", OSError, ValueError
    )


def _resolve(
    repo: Path,
    path: Path,
    key: str,
    answer: str,
    source: str,
) -> dict[str, Any]:
    current = state.read_json(path) or {}
    if current.get("status") != "pending" or current.get("id") != key:
        raise ValueError("this answer does not belong to the pending decision")
    answer = next(
        (
            option
            for option in current.get("options", ())
            if option.strip().casefold() == answer.strip().casefold()
        ),
        answer,
    )
    if answer not in current.get("options", ()):
        raise ValueError("the human reply does not select an offered option")
    if source != current.get("transport"):
        raise ValueError("the answer arrived through a different interaction")
    if answer.casefold() not in ("revise", "stop", "not now") and any(
        _digest(repo / name) != digest for name, digest in current.get("artifacts", ())
    ):
        raise ValueError(
            "the reviewed artifact changed; return to its review before approving"
        )
    updated = {**current, "status": "answered", "answer": answer}
    state.write_json(path, updated)
    return updated


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status(repo: Path, work_session_id: str | None = None) -> str:
    return json.dumps(record(repo, work_session_id) or {"status": "absent"})


def status_command(command: str, repo: Path, cwd: str = "") -> bool:
    try:
        args = shlex.split(command)
    except ValueError:
        return False
    return (
        len(args) >= 3
        and args[1:3] == ["decision", "status"]
        and policies.control_command(
            shlex.join([args[0], "policies", "status", *args[3:]]), repo, cwd
        )
    )
