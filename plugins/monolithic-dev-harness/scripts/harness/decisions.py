"""A durable pending human decision; only trusted prompt/answer hooks resolve it."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, fmap
from harness import commands, questions, state

RELATIVE_PATH = Path(".harness/state/decision.json")


@dataclass(frozen=True)
class Pending:
    """A decision waiting for the human, with the scope it is stored in (None: project-wide)."""

    id: str
    question: str
    options: tuple[str, ...]
    transport: str
    approval: bool
    scope: str | None
    presentation_id: str = ""

    @classmethod
    def from_record(cls, value: dict[str, Any], scope: str | None) -> Pending:
        return cls(
            id=str(value.get("id", "")),
            question=str(value.get("question", "")),
            options=tuple(str(option) for option in value.get("options", ())),
            transport=str(value.get("transport", "")),
            approval=bool(value.get("approval")),
            scope=scope,
            presentation_id=str(value.get("presentation_id", "")),
        )

    def matches_presentation(self, question: dict[str, Any], transport: str) -> bool:
        """Whether a question being shown is this decision's prepared presentation."""
        return (
            self.transport in ("blocking", "async")
            and self.transport == transport
            and (
                question.get("id") == self.id
                or (transport == "async" and question.get("question") == self.question)
            )
            and not self.presentation_id
        )


def _path(
    repo: Path, work_session_id: str | None, *, active: bool = False
) -> Result[Path]:
    from harness import work_sessions

    return fmap(
        work_sessions.scope_folder(repo, work_session_id, active=active),
        lambda folder: folder / "decision.json",
    )


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


def blocking(repo: Path, work_session_id: str | None) -> bool:
    """The one gate: whether a pending decision holds work done from this scope.

    A project-wide decision holds everyone; a session's decision holds that session. Work with no
    session (an unbound conversation, or a host that gives no session id) is held by any pending
    decision, so it can never act around one.
    """
    return (
        any_waiting(repo) if work_session_id is None else waiting(repo, work_session_id)
    )


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


def pending(repo: Path, work_session_id: str | None = None) -> Pending | None:
    """The decision this scope's user is answering.

    The scope's own, else the project-wide one; without a session (Cursor gives none), the one
    pending session decision. With several, none is guessed.
    """
    for scope in (work_session_id, None) if work_session_id else (None,):
        value = record(repo, scope)
        if value and value.get("status") == "pending":
            return Pending.from_record(value, scope)
    if work_session_id is None:
        match _pending_sessions(repo):
            case [(session_id, only)]:
                return Pending.from_record(only, session_id)
    return None


def _pending_sessions(repo: Path) -> list[tuple[str, dict[str, Any]]]:
    from harness import work_sessions

    match work_sessions.list_sessions(repo):
        case Ok(sessions):
            found = [
                (session.id, state.read_json(session.folder / "decision.json") or {})
                for session in sessions
            ]
            return [
                (sid, value) for sid, value in found if value.get("status") == "pending"
            ]
        case Err():
            return []


def new_key() -> str:
    return "HD-" + secrets.token_hex(8)


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
    if questions.choice_label(
        answer
    ).casefold() not in questions.DECLINE_LABELS and any(
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


def status_command(command: str, cwd: Path) -> bool:
    """Whether a shell command only reads decision or suspension status.

    The decision gate lets it run so the agent can see what it is waiting for; it never skips
    the rules. Anything but exactly one status invocation disqualifies it.
    """
    match commands.harness_args(command, cwd):
        case ("decision" | "suspension", "status", *options):
            return len(options) % 2 == 0 and all(
                flag in ("--repo", "--session-id") for flag in options[::2]
            )
        case _:
            return False
