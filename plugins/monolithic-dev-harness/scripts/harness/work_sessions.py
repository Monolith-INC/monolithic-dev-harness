"""Project-linked work sessions with local, independent lifecycle records.

These records keep a request and its progress separate from the checkout-bound implementation
session in :mod:`harness.sessions`. They require no tracker, Git branch, or project registration.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, fmap, require

from . import state

VERSION = 1
ROOT = Path(".harness") / "state" / "work_sessions"


class Status(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETE = "complete"


@dataclass(frozen=True)
class Session:
    id: str
    project_root: Path
    request: str
    status: Status
    created_at: str
    updated_at: str
    events: tuple[dict[str, str], ...]
    folder: Path


def scope_folder(
    project: Path, work_session_id: str | None, *, active: bool = False
) -> Result[Path]:
    """Where a scope keeps its records: the project's state folder, or the session's own."""
    if work_session_id is None:
        return Ok(state.state_dir(project))
    selected = (
        require_active(project, work_session_id)
        if active
        else select(project, work_session_id)
    )
    return fmap(selected, lambda session: session.folder)


def root(project: Path) -> Path:
    return project.resolve() / ROOT


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _payload(session: Session) -> dict[str, Any]:
    return {
        "version": VERSION,
        "id": session.id,
        "project_root": str(session.project_root),
        "request": session.request,
        "status": session.status.value,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "events": list(session.events),
    }


def _from_payload(
    folder: Path, payload: dict[str, Any], project: Path
) -> Result[Session]:
    expected_root = project.resolve()
    try:
        session = Session(
            id=str(payload["id"]),
            project_root=Path(str(payload["project_root"])).resolve(),
            request=str(payload["request"]),
            status=Status(str(payload["status"])),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            events=tuple(
                {"type": str(event["type"]), "at": str(event["at"])}
                for event in payload["events"]
            ),
            folder=folder,
        )
    except (KeyError, TypeError, ValueError):
        return err(
            "session_unreadable", f"work session {folder.name} has an invalid record"
        )
    return bind(
        require(
            payload.get("version") == VERSION,
            "session_unreadable",
            f"work session {folder.name} uses an unsupported version",
        ),
        lambda _: fmap(
            require(
                session.project_root == expected_root and session.id == folder.name,
                "session_unreadable",
                f"work session {folder.name} does not belong to this project",
            ),
            lambda _: session,
        ),
    )


def _read(project: Path, folder: Path) -> Result[Session]:
    return bind(
        attempt(
            lambda: json.loads((folder / "session.json").read_text(encoding="utf-8")),
            "session_unreadable",
            f"could not read work session {folder.name}",
            OSError,
            ValueError,
        ),
        lambda payload: (
            _from_payload(folder, payload, project)
            if isinstance(payload, dict)
            else err(
                "session_unreadable", f"work session {folder.name} is not an object"
            )
        ),
    )


def start(project: Path, request: str) -> Result[Session]:
    normalized = request.strip()
    return bind(
        require(
            bool(normalized),
            "invalid_request",
            "a work session needs the original request",
        ),
        lambda _: attempt(
            lambda: _create(project.resolve(), normalized),
            "session_unwritable",
            "could not create a work session",
            OSError,
        ),
    )


def _create(project: Path, request: str) -> Session:
    state.ensure_local_exclude(project)
    identifier = "WS-" + secrets.token_hex(6)
    sessions_root = root(project)
    folder = sessions_root / identifier
    staging = sessions_root / ("." + identifier + ".tmp")
    now = _now()
    session = Session(
        id=identifier,
        project_root=project,
        request=request,
        status=Status.ACTIVE,
        created_at=now,
        updated_at=now,
        events=({"type": "started", "at": now},),
        folder=folder,
    )
    staging.mkdir(parents=True, exist_ok=False)
    try:
        state.write_json(staging / "session.json", _payload(session))
        staging.rename(folder)
    except BaseException:
        if staging.exists():
            import shutil

            shutil.rmtree(staging)
        raise
    return session


def list_sessions(project: Path) -> Result[tuple[Session, ...]]:
    folders = tuple(
        sorted(path.parent for path in root(project).glob("*/session.json"))
    )
    return _read_many(project.resolve(), folders)


def route(project: Path, request: str) -> Result[dict[str, Any]]:
    """Return exact-request candidates without changing session state."""
    normalized = " ".join(request.split()).casefold()
    return bind(
        require(
            bool(normalized),
            "invalid_request",
            "session routing needs the original request",
        ),
        lambda _: bind(
            list_sessions(project),
            lambda sessions: Ok(_route(request, normalized, sessions)),
        ),
    )


def _route(
    request: str,
    normalized_request: str,
    sessions: tuple[Session, ...],
) -> dict[str, Any]:
    matches = tuple(
        session
        for session in sessions
        if " ".join(session.request.split()).casefold() == normalized_request
    )
    candidates = tuple(
        session
        for session in sessions
        if session.status in (Status.ACTIVE, Status.PAUSED, Status.STOPPED)
    )
    match matches, candidates:
        case (session,), _ if session.status == Status.ACTIVE:
            action = "continue_active"
            selected = session.id
        case _, ():
            action = "start_new"
            selected = None
        case _:
            action = "ask_user"
            selected = None
    return {
        "request": request,
        "action": action,
        "session_id": selected,
        "matches": [as_json(session) for session in matches],
        "candidates": [as_json(session) for session in candidates],
    }


def _read_many(project: Path, folders: tuple[Path, ...]) -> Result[tuple[Session, ...]]:
    match folders:
        case ():
            return Ok(())
        case (first, *rest):
            return bind(
                _read(project, first),
                lambda session: bind(
                    _read_many(project, tuple(rest)),
                    lambda sessions: Ok(
                        tuple(
                            sorted(
                                (session, *sessions),
                                key=lambda item: (item.created_at, item.id),
                            )
                        )
                    ),
                ),
            )


def select(project: Path, identifier: str) -> Result[Session]:
    return bind(
        attempt(
            lambda: state.safe_name(identifier),
            "invalid_request",
            "invalid work-session id",
            ValueError,
        ),
        lambda safe: _select(project, safe),
    )


def require_active(project: Path, identifier: str) -> Result[Session]:
    return bind(
        select(project, identifier),
        lambda session: fmap(
            require(
                session.status == Status.ACTIVE,
                "session_not_active",
                f"work session {session.id} is {session.status.value}; resume it before continuing",
            ),
            lambda _: session,
        ),
    )


def _select(project: Path, identifier: str) -> Result[Session]:
    folder = root(project) / identifier
    return bind(
        require(
            (folder / "session.json").is_file(),
            "session_not_found",
            f"work session {identifier} was not found in this project",
        ),
        lambda _: _read(project.resolve(), folder),
    )


TRANSITIONS = {
    ("pause", Status.ACTIVE): ("paused", Status.PAUSED),
    ("stop", Status.ACTIVE): ("stopped", Status.STOPPED),
    ("stop", Status.PAUSED): ("stopped", Status.STOPPED),
    ("resume", Status.PAUSED): ("resumed", Status.ACTIVE),
    ("resume", Status.STOPPED): ("resumed", Status.ACTIVE),
    ("complete", Status.ACTIVE): ("completed", Status.COMPLETE),
    ("complete", Status.PAUSED): ("completed", Status.COMPLETE),
    ("complete", Status.STOPPED): ("completed", Status.COMPLETE),
}


def transition(project: Path, identifier: str, operation: str) -> Result[Session]:
    return bind(
        select(project, identifier),
        lambda current: _transition(current, operation),
    )


def _transition(current: Session, operation: str) -> Result[Session]:
    match TRANSITIONS.get((operation, current.status)):
        case None:
            return err(
                "invalid_transition",
                f"a {current.status.value} work session cannot {operation}",
            )
        case (event, status):
            now = _now()
            updated = replace(
                current,
                status=status,
                updated_at=now,
                events=(*current.events, {"type": event, "at": now}),
            )
            return bind(
                attempt(
                    lambda: state.write_json(
                        current.folder / "session.json", _payload(updated)
                    ),
                    "session_unwritable",
                    f"could not update work session {current.id}",
                    OSError,
                ),
                lambda _: Ok(updated),
            )


def as_json(session: Session) -> dict[str, Any]:
    return _payload(session)
