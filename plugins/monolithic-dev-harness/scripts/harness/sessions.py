"""Session lifecycle and exact checkout binding for scoped harness enforcement."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from harness import gitstate

ROOT = Path(".harness") / "state" / "sessions"


class SessionError(ValueError):
    """A session cannot be created or resolved safely."""


@dataclass(frozen=True)
class Resolution:
    state: str
    session_id: str | None = None
    reason: str = ""


def _read(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"invalid session record: {exc}") from exc
    if not isinstance(value, dict):
        raise SessionError("session record must be an object")
    return value


def _write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _identity(repo: Path) -> tuple[str, str, str]:
    return (
        str(repo.resolve()),
        gitstate.git(repo, "rev-parse", "--git-dir"),
        gitstate.git(repo, "symbolic-ref", "--quiet", "HEAD"),
    )


def _session_id(identity: tuple[str, str, str], work_item: str) -> str:
    return "HS-" + hashlib.sha256(":".join((*identity, work_item)).encode()).hexdigest()[:10].upper()


def start(repo: Path, work_item: str, workflow: str) -> dict[str, object]:
    identity = _identity(repo)
    session_id = _session_id(identity, work_item)
    directory = repo / ROOT / session_id
    if (directory / "session.json").exists():
        raise SessionError(f"session already exists: {session_id}")
    record = {"session_id": session_id, "work_item": work_item, "workflow": workflow, "worktree": identity[0], "git_dir": identity[1], "branch": identity[2], "base_commit": gitstate.head_sha(repo)}
    _write(directory / "session.json", record)
    _write(directory / "events" / "0001-started.json", {"type": "started"})
    return record


def resolve(repo: Path) -> Resolution:
    try:
        identity = _identity(repo)
    except gitstate.GitError as exc:
        return Resolution("dormant", reason=str(exc))
    matches = tuple(
        (path.parent, _read(path))
        for path in (repo / ROOT).glob("*/session.json")
        if tuple(_read(path).get(key) for key in ("worktree", "git_dir", "branch")) == identity
    )
    if not matches:
        return Resolution("dormant")
    if len(matches) != 1:
        return Resolution("error", reason="multiple session bindings match this checkout")
    directory, record = matches[0]
    events = sorted((directory / "events").glob("*.json"))
    event = _read(events[-1]).get("type") if events else "corrupt"
    return Resolution("active" if event in {"started", "resumed"} else "dormant", str(record.get("session_id")), str(event))


def transition(repo: Path, session_id: str, event: str) -> Resolution:
    if event not in {"paused", "resumed", "closed"}:
        raise SessionError("event must be paused, resumed, or closed")
    directory = repo / ROOT / session_id
    record = _read(directory / "session.json")
    current = resolve(repo)
    if current.session_id != session_id:
        raise SessionError("session is not bound to this checkout")
    if event == "resumed" and current.reason != "paused":
        raise SessionError("only a paused session can resume")
    if event in {"paused", "closed"} and current.state != "active":
        raise SessionError("only an active session can pause or close")
    sequence = len(tuple((directory / "events").glob("*.json"))) + 1
    _write(directory / "events" / f"{sequence:04d}-{event}.json", {"type": event})
    return Resolution(event, str(record["session_id"]))
