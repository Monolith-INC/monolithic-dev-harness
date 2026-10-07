"""Bind host-owned conversation ids to project work sessions at the host boundary.

A conversation is bound once, by the first session-scoped harness command it runs, and switches
through an exact `harness work-session select|resume <id>` or a successfully completed `begin`.
The startup adapter pairs trusted pre/post events and protected completion evidence before binding.
The pending-decision guard runs first, so a pending question cannot be escaped by switching work.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.result import Err, Failure, Ok, Result, attempt, bind, fmap, require
from harness import commands, decisions, state, work_sessions

VERSION = 1
ROOT = Path(".harness") / "state" / "host_sessions"
HOSTS = frozenset(("codex", "claude", "cursor"))
# `resume` reactivates its session, so it may target one that is paused or stopped.
BINDABLE = {
    "select": frozenset({work_sessions.Status.ACTIVE}),
    "resume": frozenset(
        {
            work_sessions.Status.ACTIVE,
            work_sessions.Status.PAUSED,
            work_sessions.Status.STOPPED,
        }
    ),
}


def _path(project: Path, host: str, host_session_id: str) -> Result[Path]:
    return bind(
        require(
            host in HOSTS and bool(host_session_id.strip()),
            "host_session_invalid",
            "host session context is missing or unsupported",
        ),
        lambda _: Ok(
            project.resolve()
            / ROOT
            / host
            / (hashlib.sha256(host_session_id.encode("utf-8")).hexdigest() + ".json")
        ),
    )


def bind_session(
    project: Path,
    host: str,
    host_session_id: str,
    work_session_id: str,
    operation: str = "select",
    *,
    startup_receipt: str = "",
) -> Result[str]:
    return bind(
        _path(project, host, host_session_id),
        lambda destination: bind(
            _bindable(project, work_session_id, operation),
            lambda session: fmap(
                attempt(
                    lambda: state.write_json(
                        destination,
                        {
                            "version": VERSION,
                            "host": host,
                            "host_session_id": host_session_id,
                            "work_session_id": session.id,
                            "consumed_startups": list(
                                dict.fromkeys(
                                    (*consumed_startups(destination),)
                                    + ((startup_receipt,) if startup_receipt else ())
                                )
                            ),
                            **{
                                key: value
                                for key, value in (
                                    ("startup_receipt", startup_receipt),
                                )
                                if value
                            },
                        },
                    ),
                    "host_session_unwritable",
                    f"could not bind this {host} session to project work",
                    OSError,
                ),
                lambda _: session.id,
            ),
        ),
    )


def consumed_startups(source: Path) -> tuple[str, ...]:
    match state.read_json(source):
        case {"consumed_startups": list() as receipts}:
            return tuple(item for item in receipts if isinstance(item, str))
        case _:
            return ()


def startup_consumed(project: Path, host: str, conversation: str, receipt: str) -> bool:
    match _path(project, host, conversation):
        case Ok(source):
            return receipt in consumed_startups(source)
        case _:
            return False


def resolve_session(
    project: Path, host: str, host_session_id: str
) -> Result[str | None]:
    return bind(
        _path(project, host, host_session_id),
        lambda source: _resolve_record(project, host, host_session_id, source),
    )


def _resolve_record(
    project: Path, host: str, host_session_id: str, source: Path
) -> Result[str | None]:
    try:
        record = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Ok(None)
    except (OSError, json.JSONDecodeError):
        return Err(
            Failure(
                "host_session_unreadable",
                f"the saved {host} work-session link cannot be read",
            )
        )
    match record:
        case {
            "version": record_version,
            "host": record_host,
            "host_session_id": record_id,
            "work_session_id": work_session_id,
        } if (
            record_version == VERSION
            and record_host == host
            and record_id == host_session_id
        ):
            return fmap(
                work_sessions.select(project, str(work_session_id)),
                lambda _: str(work_session_id),
            )
        case _:
            return Err(
                Failure(
                    "host_session_unreadable",
                    f"the saved {host} work-session link is invalid",
                )
            )


def _bindable(
    project: Path, work_session_id: str, operation: str
) -> Result[work_sessions.Session]:
    return bind(
        work_sessions.select(project, work_session_id),
        lambda session: fmap(
            require(
                session.status in BINDABLE[operation],
                "session_not_active",
                f"work session {session.id} is {session.status.value}; it cannot be chosen",
            ),
            lambda _: session,
        ),
    )


def requested(command: str, cwd: Path) -> tuple[str, str] | None:
    """(work session, how) a shell command asks this conversation to work in, if any.

    `how` is `select` or `resume` for an explicit switch, `named` when a session-scoped
    `workflow` or `decision` command names its session.
    """
    match commands.harness_args(command, cwd):
        case ("begin", *rest) if "--new" not in rest:
            match commands.option(tuple(rest), "--session"):
                case str() as identifier:
                    return identifier, "begin"
                case _:
                    return None
        case ("work-session", "select" | "resume" as how, identifier, *_):
            return identifier, how
        case ("workflow" | "decision", *rest):
            named = commands.option(tuple(rest), "--session-id")
            return (named, "named") if named else None
        case _:
            return None


def recovery_allowed(
    project: Path, current: str | None, request: tuple[str, str] | None
) -> bool:
    """Recover a pending scope without leaving another unanswered conversation."""
    match request:
        case (identifier, "begin") if not decisions.waiting(project):
            return current == identifier or (
                current is None and decisions.pending(project, identifier) is not None
            )
        case _:
            return False


def mismatch(current: str | None, request: tuple[str, str] | None) -> Failure | None:
    """A command that names another session than the one this conversation works in."""
    match request:
        case (named, "named") if current is not None and named != current:
            return Failure(
                "work_session_mismatch",
                f"this conversation works on {current}; switch with "
                f"`harness work-session select {named}` before working on {named}",
            )
        case _:
            return None


def bind_requested(
    project: Path,
    host: str,
    host_session_id: str,
    current: str | None,
    request: tuple[str, str] | None,
) -> Result[str | None]:
    """Bind an allowed request: a switch always, a named session only for an unbound conversation."""
    match request:
        case (identifier, "select" | "resume" as how) if host_session_id:
            return bind_session(project, host, host_session_id, identifier, how)
        case (identifier, "named") if host_session_id and current is None:
            return bind_session(project, host, host_session_id, identifier)
        case _:
            return Ok(current)


def for_payload(
    project: Path, host: str, payload: dict[str, Any]
) -> Result[str | None]:
    from host_adapters import native_session_id

    host_session_id = native_session_id(host, payload)
    return (
        resolve_session(project, host, host_session_id) if host_session_id else Ok(None)
    )
