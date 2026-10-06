"""Bind host-owned conversation ids to project work sessions at the host boundary."""

from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

from core.result import Err, Failure, Ok, Result, attempt, bind, fmap, require
from harness import state, work_sessions
from policy.events import CanonicalToolEvent

VERSION = 1
ROOT = Path(".harness") / "state" / "host_sessions"
HOSTS = frozenset(("codex", "claude", "cursor"))


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
    project: Path, host: str, host_session_id: str, work_session_id: str
) -> Result[str]:
    return bind(
        _path(project, host, host_session_id),
        lambda destination: bind(
            work_sessions.select(project, work_session_id),
            lambda session: fmap(
                attempt(
                    lambda: state.write_json(
                        destination,
                        {
                            "version": VERSION,
                            "host": host,
                            "host_session_id": host_session_id,
                            "work_session_id": session.id,
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


def _explicit_work_session(command: str) -> Result[str | None]:
    try:
        words = tuple(shlex.split(command))
    except ValueError:
        return Ok(None)
    commands = tuple(
        index
        for index, word in enumerate(words)
        if word == "harness"
        or word.endswith("/bin/harness")
        or word.endswith("/scripts/harness/cli.py")
    )
    for index in commands:
        args = words[index + 1 :]
        match args:
            case ("workflow" | "decision", *_):
                if "--session-id" not in args:
                    continue
                position = args.index("--session-id")
                return (
                    Ok(args[position + 1])
                    if position + 1 < len(args)
                    else Err(
                        Failure(
                            "host_session_invalid",
                            "a session-scoped harness command needs a work-session id",
                        )
                    )
                )
            case ("work-session", operation, identifier, *_):
                if operation in ("select", "resume"):
                    return Ok(identifier)
            case _:
                continue
    return Ok(None)


def for_event(project: Path, event: CanonicalToolEvent) -> Result[str | None]:
    """Bind explicit session commands, otherwise resolve the current host conversation."""
    if not event.host_session_id:
        return Ok(None)
    return bind(
        _explicit_work_session(event.command or ""),
        lambda requested: (
            bind_session(
                project,
                event.client,
                event.host_session_id,
                requested,
            )
            if requested
            else resolve_session(project, event.client, event.host_session_id)
        ),
    )


def for_payload(
    project: Path, host: str, payload: dict[str, Any]
) -> Result[str | None]:
    from host_adapters import native_session_id

    host_session_id = native_session_id(host, payload)
    return (
        resolve_session(project, host, host_session_id) if host_session_id else Ok(None)
    )
