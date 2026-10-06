"""Harness state under `<repo>/.harness/state/`: approvals, manual checks, check evidence, review verdicts.

Only the hooks write approvals and manual-check records, and only from what the user typed or
clicked, so only a human can open a write window or vouch for a manual check. Check evidence and review verdicts are written by
the stage scripts and keyed to git tree/commit ids, so they go stale the moment the code changes.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.result import Err, Ok

STATE_RELATIVE_PATH = Path(".harness") / "state"
# Harness state and local tracker records belong to one clone: never committed, shared, or adopted.
LOCAL_ONLY_PATHS = (".harness/state/", ".harness/tracker/")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def state_dir(repo: Path) -> Path:
    return repo / STATE_RELATIVE_PATH


def ensure_local_exclude(repo: Path) -> tuple[str, ...]:
    """Keep clone-local records out of Git, including before repository bootstrap."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    match result.returncode, result.stdout.strip():
        case 0, str() as location if location:
            path = Path(location)
            resolved = path if path.is_absolute() else repo / path
            lines = (
                resolved.read_text(encoding="utf-8").splitlines()
                if resolved.exists()
                else []
            )
            added = tuple(entry for entry in LOCAL_ONLY_PATHS if entry not in lines)
            match added:
                case ():
                    return ()
                case _:
                    resolved.parent.mkdir(parents=True, exist_ok=True)
                    resolved.write_text(
                        "\n".join([*lines, *added]) + "\n", encoding="utf-8"
                    )
                    return added
        case _:
            return ()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Replace a state file atomically: readers see the old record or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def safe_name(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise ValueError(f"invalid state name: {name!r}")
    return name


# --- approvals (approval-required) ------------------------------------------------------------


def open_approval(
    repo: Path,
    approval_id: str,
    minutes: int,
    question: str = "",
    work_session_id: str | None = None,
) -> dict[str, Any]:
    """A window for tracker/SCM writes, scoped to the work session it was opened in.

    Without a work session (Cursor, or a project with none bound) the window is project-wide.
    """
    now = _now()
    record: dict[str, Any] = {
        "id": approval_id,
        "opened": now.isoformat(),
        "expires": (now + timedelta(minutes=minutes)).isoformat(),
        "writes": [],
    }
    if question:
        record["question"] = question
    if work_session_id is not None:
        record["work_session"] = work_session_id
    write_json(state_dir(repo) / "approvals" / f"{safe_name(approval_id)}.json", record)
    return record


def revoke_approvals(repo: Path, work_session_id: str | None = None) -> int:
    """Close open windows: one work session's, or every window when none is named."""
    directory = state_dir(repo) / "approvals"
    count = 0
    for path in directory.glob("*.json") if directory.is_dir() else []:
        record = read_json(path)
        if (
            record
            and (work_session_id is None or _scope(record) == work_session_id)
            and datetime.fromisoformat(record["expires"]) > _now()
        ):
            record["expires"] = _now().isoformat()
            record["revoked"] = True
            write_json(path, record)
            count += 1
    return count


def _scope(record: dict[str, Any]) -> str | None:
    scope = record.get("work_session")
    return scope if isinstance(scope, str) else None


def active_approval(
    repo: Path, work_session_id: str | None = None
) -> tuple[Path, dict[str, Any]] | None:
    """The newest open window for exactly this work session; `None` means project-wide only."""
    directory = state_dir(repo) / "approvals"
    if not directory.is_dir():
        return None
    best: tuple[Path, dict[str, Any]] | None = None
    for path in directory.glob("*.json"):
        record = read_json(path)
        if not record or "expires" not in record or _scope(record) != work_session_id:
            continue
        try:
            expires = datetime.fromisoformat(record["expires"])
        except ValueError:
            continue
        if expires > _now() and (best is None or record["opened"] > best[1]["opened"]):
            best = (path, record)
    return best


def pin_notes(repo: Path, approval_id: str, notes: dict[str, str]) -> None:
    """Record the approved plan and spec notes (path -> content digest) this approval covers."""
    path = state_dir(repo) / "approvals" / f"{safe_name(approval_id)}.json"
    record = read_json(path)
    if record is None or not notes:
        return
    pinned = record.get("notes")
    record["notes"] = {**(pinned if isinstance(pinned, dict) else {}), **notes}
    write_json(path, record)


def pinned_notes(repo: Path) -> dict[str, set[str]]:
    """Path -> digests pinned by approvals the user has not revoked. Expiry does not unpin."""
    directory = state_dir(repo) / "approvals"
    pinned: dict[str, set[str]] = {}
    for path in directory.glob("*.json") if directory.is_dir() else []:
        record = read_json(path)
        notes = record.get("notes") if record and not record.get("revoked") else None
        for note, digest in notes.items() if isinstance(notes, dict) else ():
            pinned.setdefault(str(note), set()).add(str(digest))
    return pinned


def log_write(path: Path, record: dict[str, Any], tool: str) -> None:
    record.setdefault("writes", []).append({"tool": tool, "at": _now().isoformat()})
    write_json(path, record)


# --- tracking mode (the gateway's skip and resume, each behind an approval) --------------------

TRACKING_MODES = ("enforced", "skipped")


def tracking_mode(repo: Path) -> str:
    mode = (read_json(state_dir(repo) / "tracking.json") or {}).get("mode")
    return mode if mode in TRACKING_MODES else "enforced"


def set_tracking_mode(repo: Path, mode: str) -> str:
    if mode not in TRACKING_MODES:
        raise ValueError(f"tracking mode must be one of {TRACKING_MODES}")
    write_json(
        state_dir(repo) / "tracking.json", {"mode": mode, "changed": _now().isoformat()}
    )
    return mode


# --- suspension (every check released, on the user's own typed request) -----------------------

HARNESS_MODES = ("active", "suspended")


def harness_mode(repo: Path) -> str:
    mode = (read_json(state_dir(repo) / "suspension.json") or {}).get("mode")
    return mode if mode in HARNESS_MODES else "active"


def set_harness_mode(repo: Path, mode: str) -> str:
    if mode not in HARNESS_MODES:
        raise ValueError(f"harness mode must be one of {HARNESS_MODES}")
    write_json(
        state_dir(repo) / "suspension.json",
        {"mode": mode, "changed": _now().isoformat()},
    )
    return mode


# --- questions shown to the user (approval by click) ------------------------------------------


def _session_record_path(
    repo: Path, folder: str, name: str, work_session_id: str | None
) -> Path:
    if work_session_id is None:
        return state_dir(repo) / folder / f"{safe_name(name)}.json"
    from harness import work_sessions

    match work_sessions.select(repo, work_session_id):
        case Ok(session):
            return session.folder / folder / f"{safe_name(name)}.json"
        case Err(failure):
            raise ValueError(failure.message)


def mark_asked(
    repo: Path,
    name: str,
    detail: dict[str, Any] | None = None,
    work_session_id: str | None = None,
) -> None:
    """Mark a question the check let through, with what the hook pinned when it was shown."""
    write_json(
        _session_record_path(repo, "asked", name, work_session_id),
        {**(detail or {}), "asked": _now().isoformat()},
    )


def take_asked(
    repo: Path, name: str, work_session_id: str | None = None
) -> dict[str, Any] | None:
    """The mark of a question the check let through, or None; the mark is used up."""
    try:
        path = _session_record_path(repo, "asked", name, work_session_id)
        record = read_json(path)
        path.unlink()
    except OSError:
        return None
    except ValueError:
        return None
    return record if record is not None else {}


# --- manual checks (guarded-paths) ------------------------------------------------------------


def record_manual(repo: Path, name: str, tree: str, note: str) -> None:
    write_json(
        state_dir(repo) / "manual" / f"{safe_name(name)}-{tree}.json",
        {"name": name, "tree": tree, "note": note, "recorded": _now().isoformat()},
    )


def has_manual(repo: Path, name: str, tree: str) -> bool:
    record = read_json(state_dir(repo) / "manual" / f"{safe_name(name)}-{tree}.json")
    return bool(record) and record.get("tree") == tree and record.get("name") == name


# --- check evidence (guarded-paths, draft-reviewed-prs) ---------------------------------------


def record_checks(repo: Path, tree: str, results: list[dict[str, Any]]) -> Path:
    path = state_dir(repo) / "checks" / f"{tree}.json"
    write_json(path, {"tree": tree, "recorded": _now().isoformat(), "results": results})
    return path


def passed_checks(repo: Path, tree: str) -> set[str]:
    record = read_json(state_dir(repo) / "checks" / f"{tree}.json")
    if not record:
        return set()
    return {r["name"] for r in record.get("results", []) if r.get("exit_code") == 0}


# --- review verdicts (draft-reviewed-prs) -----------------------------------------------------


def record_review(repo: Path, head: str, verdict: str, summary: str) -> Path:
    if verdict not in {"ready", "blocked"}:
        raise ValueError("verdict must be 'ready' or 'blocked'")
    path = state_dir(repo) / "review" / f"{head}.json"
    write_json(
        path,
        {
            "head": head,
            "verdict": verdict,
            "summary": summary,
            "recorded": _now().isoformat(),
        },
    )
    return path


def review_verdict(repo: Path, head: str) -> str | None:
    record = read_json(state_dir(repo) / "review" / f"{head}.json")
    return record.get("verdict") if record else None
