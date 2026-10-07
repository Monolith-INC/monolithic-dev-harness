"""A durable pending human decision; only trusted prompt/answer hooks resolve it."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err, fmap
from harness import commands, questions, state

RELATIVE_PATH = Path(".harness/state/decision.json")
HISTORY = "decision-history.json"
HISTORY_KEPT = 50


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
    allow_free_text: bool = False
    details: tuple[str, ...] = ()

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
            allow_free_text=bool(value.get("allow_free_text"))
            and not bool(value.get("approval")),
            details=tuple(str(detail) for detail in value.get("details", ())),
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

    A linked conversation: its session's own, else the project-wide one. A conversation with no
    link (Cursor gives none): the project's current session's, where commands that name no
    session ask, else the project-wide one, else the one pending session decision. With several,
    none is guessed; a linked conversation never answers another session's question.
    """
    from harness import work_sessions

    first = work_session_id or work_sessions.current(repo)
    for scope in (first, None) if first else (None,):
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
    allow_free_text: bool = False,
    details: tuple[str, ...] = (),
    gate: str = "",
    binds: dict[str, Any] | None = None,
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
                allow_free_text,
                details,
                gate,
                binds,
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
    allow_free_text: bool,
    details: tuple[str, ...] = (),
    gate: str = "",
    binds: dict[str, Any] | None = None,
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
        or len(details) > len(options)
        or (allow_free_text and (approval or questions.authorizing_options(options)))
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
        "allow_free_text": allow_free_text,
        "details": details,
    }
    if gate:
        value["gate"] = gate
    if binds is not None:
        value["binds"] = binds
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
    answer = questions.match_option(answer, tuple(current.get("options", ()))) or answer
    if answer not in current.get("options", ()) and not _free_text_allowed(
        current, answer
    ):
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
    history = path.with_name(HISTORY)
    earlier = (state.read_json(history) or {}).get("answers", [])
    state.write_json(history, {"answers": [*earlier, updated][-HISTORY_KEPT:]})
    return updated


def reusable(
    repo: Path,
    question: str,
    options: tuple[str, ...],
    artifacts: tuple[tuple[str, str], ...],
    approval: bool,
    *,
    work_session_id: str | None = None,
    target: tuple[str, str] | None = None,
) -> dict[str, Any] | None:
    """An earlier answer to this same question about the same, unchanged content or target.

    Only context-bound questions are reused: a question without reviewed files or a target may
    mean something new each time it is asked. A decline is never reused, so the human can change their mind. An
    approval is reused only while the write window it opened is still open; once it closes, only a
    new human reply can open another (ADR-0003).
    """
    if not artifacts and not target:
        return None
    match _path(repo, work_session_id):
        case Ok(path):
            history = (state.read_json(path.with_name(HISTORY)) or {}).get(
                "answers", []
            )
        case Err():
            return None
    labels = {questions.choice_label(option).casefold() for option in options}
    for entry in reversed(history):
        if (
            entry.get("question", "").strip().casefold() == question.strip().casefold()
            and {questions.choice_label(o).casefold() for o in entry.get("options", ())}
            == labels
            and bool(entry.get("approval")) == approval
            and [tuple(pair) for pair in entry.get("artifacts", ())] == list(artifacts)
            and _entry_target(entry) == target
            and questions.choice_label(str(entry.get("answer", ""))).casefold()
            not in questions.DECLINE_LABELS
        ):
            return (
                entry
                if not approval or _window_open(repo, entry, work_session_id)
                else None
            )
    return None


def _window_open(repo: Path, entry: dict[str, Any], scope: str | None) -> bool:
    """Whether the approval this answer opened still holds (not revoked, expired, or ended)."""
    wanted = questions.approval_id(str(entry.get("id", "")))
    return any(
        record.get("id") == wanted for _, record in state.open_approvals(repo, scope)
    )


def _entry_target(entry: dict[str, Any]) -> tuple[str, str] | None:
    match (entry.get("binds") or {}).get("target"):
        case [kind, value]:
            return (str(kind), str(value))
        case _:
            return None


def approval_binds(record: dict[str, Any]) -> dict[str, Any] | None:
    """What an answered gate's approval is tied to: its reviewed files and target, if any."""
    match record.get("binds"):
        case {"bound": True, "target": target}:
            bound: dict[str, Any] = {"artifacts": list(record.get("artifacts", ()))}
            if target:
                bound["target"] = list(target)
            return bound
        case _:
            return None


def _free_text_allowed(current: dict[str, Any], answer: str) -> bool:
    return (
        bool(current.get("allow_free_text"))
        and not current.get("approval")
        and not questions.authorizing_options(tuple(current.get("options", ())))
        and bool(answer.strip())
    )


def fallback(
    repo: Path,
    transport: str,
    *,
    work_session_id: str | None = None,
) -> Result[dict[str, Any]]:
    """Move the same unanswered review to a simpler delivery method; never answer it."""
    return bind(
        _path(repo, work_session_id),
        lambda path: bind(
            _fallback_record(state.read_json(path) or {}, transport),
            lambda updated: fmap(
                attempt(
                    lambda: state.write_json(path, updated),
                    "decision_invalid",
                    "question fallback",
                    OSError,
                ),
                lambda _: updated,
            ),
        ),
    )


def _fallback_record(current: dict[str, Any], transport: str) -> Result[dict[str, Any]]:
    match current.get("status"), current.get("transport"), transport:
        case "pending", "blocking", "async" | "chat":
            return Ok({**current, "transport": transport, "presentation_id": ""})
        case "pending", "async", "chat":
            return Ok({**current, "transport": transport, "presentation_id": ""})
        case "pending", "chat", "chat":
            return Ok(current)
        case _:
            return err(
                "decision_invalid",
                "fallback requires a pending question and a simpler transport",
            )


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


def fallback_command(command: str, cwd: Path) -> bool:
    """Only the controlled transport change may pass the waiting gate."""
    match commands.harness_args(command, cwd):
        case ("decision", "fallback", *options):
            return _fallback_options(tuple(options))
        case _:
            return False


def _fallback_options(options: tuple[str, ...]) -> bool:
    match options:
        case ():
            return True
        case ("--async-available", *rest):
            return _fallback_options(tuple(rest))
        case ("--repo" | "--session-id" | "--host", value, *rest) if (
            not value.startswith("--")
        ):
            return _fallback_options(tuple(rest))
        case _:
            return False
