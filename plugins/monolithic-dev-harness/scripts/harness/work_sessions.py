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
    implicit_selection: bool = True


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
        "implicit_selection": session.implicit_selection,
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
            implicit_selection=payload.get("implicit_selection", True) is True,
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
    return bind(
        create(project, request, implicit_selection=True),
        lambda selected: attempt(
            lambda: _remembered(project, selected),
            "session_unwritable",
            "could not select the created work session",
            OSError,
        ),
    )


def create(
    project: Path, request: str, *, implicit_selection: bool = False
) -> Result[Session]:
    """Create durable work without selecting it; startup selects only after validation."""
    return bind(
        require(
            bool(request.strip()),
            "invalid_request",
            "a work session needs the original request",
        ),
        lambda _: attempt(
            lambda: _create(project.resolve(), request.strip(), implicit_selection),
            "session_unwritable",
            "could not create a work session",
            OSError,
        ),
    )


def _remembered(project: Path, session: Session) -> Session:
    remember_current(project, session.id)
    return session


def _create(project: Path, request: str, implicit_selection: bool) -> Session:
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
        implicit_selection=implicit_selection,
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


CURRENT = "current.json"


def remember_current(project: Path, identifier: str) -> None:
    """Record the session the project is working in, so nobody has to repeat its id."""
    state.write_json(
        root(project) / CURRENT,
        {
            "id": identifier,
            "selected": sorted(set((*_selected(project), identifier))),
        },
    )


def _selected(project: Path) -> tuple[str, ...]:
    match state.read_json(root(project) / CURRENT):
        case {"selected": list() as selected}:
            return tuple(item for item in selected if isinstance(item, str))
        case {"id": str() as identifier}:
            return (identifier,)
        case _:
            return ()


def current(project: Path) -> str | None:
    """The work session commands and questions belong to when none is named.

    The one last started, resumed, or selected while it is still active; else the only active
    session; else none, and the work is project-wide. Never an error: talking to the human must
    not depend on a session existing.
    """
    match list_sessions(project):
        case Ok(sessions):
            return _current_active(
                tuple(
                    s.id
                    for s in sessions
                    if s.status == Status.ACTIVE
                    and (s.implicit_selection or s.id in _selected(project))
                ),
                (state.read_json(root(project) / CURRENT) or {}).get("id"),
            )
        case _:
            return None


def _current_active(active: tuple[str, ...], remembered: object) -> str | None:
    match active:
        case _ if remembered in active:
            return str(remembered)
        case (identifier,):
            return identifier
        case _:
            return None


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


def transition(
    project: Path, identifier: str, operation: str, *, make_current: bool = True
) -> Result[Session]:
    return bind(
        select(project, identifier),
        lambda current: _transition(current, operation, make_current),
    )


def _save_transition(updated: Session, make_current: bool) -> Session:
    state.write_json(updated.folder / "session.json", _payload(updated))
    match updated.status, make_current:
        case Status.ACTIVE, True:
            remember_current(updated.project_root, updated.id)
        case _:
            pass
    return updated


def _transition(
    current: Session, operation: str, make_current: bool
) -> Result[Session]:
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
                    lambda: _save_transition(updated, make_current),
                    "session_unwritable",
                    f"could not update work session {current.id}",
                    OSError,
                ),
                lambda _: Ok(updated),
            )


def as_json(session: Session) -> dict[str, Any]:
    return _payload(session)
