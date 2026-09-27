"""A session binds one work item to one checkout, and scopes enforcement to it.

    .harness/state/sessions/<id>/session.json          what is bound: work item, checkout, base commit
    .harness/state/sessions/<id>/events/0001-started   what happened since, in order

A checkout is the worktree folder, its git directory, and its branch. Governed code changes need an
active session for the checkout they happen in, and the session names the work item they belong
to, so the workflow checks that item rather than guessing it again from the branch name. A paused
or missing session blocks those changes; a closed one frees the checkout, and the same work item
can start a new session later.

The folder is human-owned for direct writes: sessions change only through this module (the
`harness session` command), which checks every transition.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from core.result import (
    Err,
    Ok,
    Result,
    attempt,
    bind,
    err,
    failures,
    fmap,
    oks,
    require,
)

from . import gitstate, state

SESSIONS = "sessions"
ATTEMPTS = 5


class Phase(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


# What each recorded event leaves the session as.
EVENTS = {
    "started": Phase.ACTIVE,
    "paused": Phase.PAUSED,
    "resumed": Phase.ACTIVE,
    "closed": Phase.CLOSED,
}
# (command, phase it applies to) -> event it records.
TRANSITIONS = {
    ("pause", Phase.ACTIVE): "paused",
    ("resume", Phase.PAUSED): "resumed",
    ("close", Phase.ACTIVE): "closed",
    ("close", Phase.PAUSED): "closed",
}


@dataclass(frozen=True)
class Checkout:
    worktree: str
    git_dir: str
    branch: str


@dataclass(frozen=True)
class Session:
    id: str
    work_item: str
    workflow: str
    checkout: Checkout
    base_commit: str
    phase: Phase
    folder: Path


@dataclass(frozen=True)
class Unbound:
    """No open session for this checkout."""

    reason: str


@dataclass(frozen=True)
class Bound:
    session: Session


@dataclass(frozen=True)
class Broken:
    """The checkout or its sessions cannot be read; enforcement treats this as a block."""

    reason: str


Resolution = Unbound | Bound | Broken


def _git(repo: Path, *args: str) -> Result[str]:
    return attempt(
        lambda: gitstate.git(repo, *args), "git_unavailable", "git", gitstate.GitError
    )


def checkout(repo: Path) -> Result[Checkout]:
    """This checkout's identity. A detached HEAD has no branch, so it cannot hold a session."""
    return bind(
        _git(
            repo,
            "rev-parse",
            "--show-toplevel",
            "--absolute-git-dir",
            "--symbolic-full-name",
            "HEAD",
        ),
        _identity,
    )


def _identity(output: str) -> Result[Checkout]:
    """One git answer: top level, git directory, and `refs/heads/<branch>` (or `HEAD` when detached)."""
    match output.splitlines():
        case [top, git_dir, ref] if ref.startswith("refs/heads/"):
            return Ok(
                Checkout(
                    str(Path(top).resolve()),
                    str(Path(git_dir).resolve()),
                    ref.removeprefix("refs/heads/"),
                )
            )
        case _:
            return err("git_unavailable", "HEAD is not on a branch")


def _root(repo: Path) -> Path:
    return state.state_dir(repo) / SESSIONS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- reading --------------------------------------------------------------------------------


def _read(path: Path) -> Result[dict]:
    return bind(
        attempt(
            lambda: json.loads(path.read_text(encoding="utf-8")),
            "session_unreadable",
            f"could not read {path}",
            OSError,
            ValueError,
        ),
        lambda value: (
            Ok(value)
            if isinstance(value, dict)
            else err("session_unreadable", f"{path} is not an object")
        ),
    )


def _events(folder: Path) -> tuple[Path, ...]:
    directory = folder / "events"
    return tuple(sorted(directory.glob("*.json"))) if directory.is_dir() else ()


def _phase(folder: Path) -> Result[Phase]:
    match _events(folder):
        case ():
            return err("session_unreadable", f"session {folder.name} has no events")
        case (*_, last):
            return bind(
                _read(last),
                lambda event: (
                    Ok(EVENTS[event["type"]])
                    if event.get("type") in EVENTS
                    else err(
                        "session_unreadable",
                        f"session {folder.name} has an unknown event",
                    )
                ),
            )


def _checkout_of(record: dict) -> Checkout:
    return Checkout(
        str(record.get("worktree", "")),
        str(record.get("git_dir", "")),
        str(record.get("branch", "")),
    )


def _session(folder: Path) -> Result[Session]:
    return bind(
        _read(folder / "session.json"),
        lambda record: fmap(
            _phase(folder),
            lambda phase: Session(
                id=str(record.get("id", folder.name)),
                work_item=str(record.get("work_item", "")),
                workflow=str(record.get("workflow", "")),
                checkout=_checkout_of(record),
                base_commit=str(record.get("base_commit", "")),
                phase=phase,
                folder=folder,
            ),
        ),
    )


def _folders(repo: Path) -> tuple[Path, ...]:
    root = _root(repo)
    return (
        tuple(sorted(path.parent for path in root.glob("*/session.json")))
        if root.is_dir()
        else ()
    )


def _claims(repo: Path, identity: Checkout) -> Result[tuple[Result[Session], ...]]:
    """This checkout's sessions. A record nobody can read may belong to any checkout, so it
    fails the lot; a readable record for another checkout is none of this checkout's business."""
    records = tuple(
        (folder, _read(folder / "session.json")) for folder in _folders(repo)
    )
    unreadable = failures(record for _, record in records)
    return (
        err("session_unreadable", unreadable[0].message)
        if unreadable
        else Ok(
            tuple(
                _session(folder)
                for folder, record in records
                if isinstance(record, Ok) and _checkout_of(record.value) == identity
            )
        )
    )


def _open(sessions: tuple[Result[Session], ...]) -> tuple[Session, ...]:
    return tuple(session for session in oks(sessions) if session.phase != Phase.CLOSED)


def resolve(repo: Path) -> Resolution:
    """The open session bound to this checkout, if exactly one is; a checkout that cannot say is broken."""
    match checkout(repo):
        case Err(failure):
            return Broken(
                f"this checkout has no branch to bind a session to ({failure.message})"
            )
        case Ok(identity):
            return _resolution(_claims(Path(identity.worktree), identity), identity)


def _resolution(
    claims: Result[tuple[Result[Session], ...]], identity: Checkout
) -> Resolution:
    match claims:
        case Err(failure):
            return Broken(
                f"a session record cannot be read ({failure.message}); a person removes that session folder"
            )
        case Ok(sessions) if failures(sessions):
            return Broken(
                f"this checkout's session record cannot be read: {failures(sessions)[0].message}"
            )
        case Ok(sessions):
            return _one(_open(sessions), identity)


def _one(sessions: tuple[Session, ...], identity: Checkout) -> Resolution:
    match sessions:
        case ():
            return Unbound(
                f"no open session on branch {identity.branch!r} in this checkout"
            )
        case (session,):
            return Bound(session)
        case several:
            return Broken(
                f"{len(several)} open sessions claim this checkout; close all but one"
            )


# --- writing --------------------------------------------------------------------------------


def _create(path: Path, payload: dict) -> Result[Path]:
    """Write a new file, refusing to replace one that exists (another process got there first)."""

    def write() -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            file.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    return attempt(write, "session_conflict", f"could not create {path.name}", OSError)


def _append(folder: Path, event: str, attempts: int = ATTEMPTS) -> Result[Path]:
    sequence_number = 1 + max(
        (int(path.name.split("-", 1)[0]) for path in _events(folder)), default=0
    )
    written = _create(
        folder / "events" / f"{sequence_number:04d}-{event}.json",
        {"type": event, "at": _now()},
    )
    match written:
        case Err() if attempts > 1:
            return _append(folder, event, attempts - 1)
        case _:
            return written


def start(repo: Path, work_item: str, workflow: str) -> Result[Session]:
    """Bind `work_item` to this checkout. The checkout must be on a branch and not already bound."""
    return bind(
        checkout(repo),
        lambda identity: bind(
            require(
                isinstance(resolve(repo), Unbound),
                "session_exists",
                f"branch {identity.branch!r} in this checkout already has a session ({describe(resolve(repo))}); close it first",
            ),
            lambda _: _begin(
                Path(identity.worktree), identity, work_item.strip(), workflow
            ),
        ),
    )


def _begin(
    repo: Path, identity: Checkout, work_item: str, workflow: str
) -> Result[Session]:
    identifier = "HS-" + secrets.token_hex(5).upper()
    folder = _root(repo) / identifier
    record = {
        "id": identifier,
        "work_item": work_item,
        "workflow": workflow,
        "worktree": identity.worktree,
        "git_dir": identity.git_dir,
        "branch": identity.branch,
        "base_commit": _head(repo),
        "started": _now(),
    }
    staging = state.state_dir(repo) / "sessions-staging" / identifier
    return bind(
        require(bool(work_item), "invalid_request", "a session needs a work item"),
        lambda _: bind(
            _create(staging / "session.json", record),
            lambda _: bind(
                _append(staging, "started"),
                lambda _: bind(_publish(staging, folder), lambda _: _session(folder)),
            ),
        ),
    )


def _publish(staging: Path, folder: Path) -> Result[Path]:
    """Move a complete session into place in one rename, so no reader sees half of it."""

    def move() -> Path:
        folder.parent.mkdir(parents=True, exist_ok=True)
        return staging.rename(folder)

    return attempt(
        move, "session_conflict", f"could not record session {folder.name}", OSError
    )


def _head(repo: Path) -> str:
    match _git(repo, "rev-parse", "HEAD"):
        case Ok(sha):
            return sha
        case Err():
            return ""  # a repository with no commits yet


def transition(repo: Path, command: str) -> Result[Session]:
    """Pause, resume, or close this checkout's session, when its phase allows it."""
    match resolve(repo):
        case Bound(session):
            event = TRANSITIONS.get((command, session.phase))
            return (
                bind(_append(session.folder, event), lambda _: _session(session.folder))
                if event
                else err(
                    "invalid_transition",
                    f"a {session.phase.value} session cannot {command}",
                )
            )
        case Unbound(reason) | Broken(reason):
            return err("no_session", reason)


def describe(resolution: Resolution) -> str:
    match resolution:
        case Bound(session):
            return f"{session.id}: {session.work_item} on {session.checkout.branch} ({session.phase.value})"
        case Unbound(reason) | Broken(reason):
            return reason
