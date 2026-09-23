"""Harness state under `<repo>/.harness/state/`: approvals, manual checks, check evidence, review verdicts.

Only the hooks write approvals and manual-check records, and only from what the user typed or
clicked, so only a human can open a write window or vouch for a manual check. Check evidence and review verdicts are written by
the stage scripts and keyed to git tree/commit ids, so they go stale the moment the code changes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STATE_RELATIVE_PATH = Path(".harness") / "state"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def state_dir(repo: Path) -> Path:
    return repo / STATE_RELATIVE_PATH


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _read(path: Path) -> dict[str, Any] | None:
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
    repo: Path, approval_id: str, minutes: int, question: str = ""
) -> dict[str, Any]:
    now = _now()
    record: dict[str, Any] = {
        "id": approval_id,
        "opened": now.isoformat(),
        "expires": (now + timedelta(minutes=minutes)).isoformat(),
        "writes": [],
    }
    if question:
        record["question"] = question
    _write(state_dir(repo) / "approvals" / f"{safe_name(approval_id)}.json", record)
    return record


def revoke_approvals(repo: Path) -> int:
    directory = state_dir(repo) / "approvals"
    count = 0
    for path in directory.glob("*.json") if directory.is_dir() else []:
        record = _read(path)
        if record and datetime.fromisoformat(record["expires"]) > _now():
            record["expires"] = _now().isoformat()
            record["revoked"] = True
            _write(path, record)
            count += 1
    return count


def active_approval(repo: Path) -> tuple[Path, dict[str, Any]] | None:
    directory = state_dir(repo) / "approvals"
    if not directory.is_dir():
        return None
    best: tuple[Path, dict[str, Any]] | None = None
    for path in directory.glob("*.json"):
        record = _read(path)
        if not record or "expires" not in record:
            continue
        try:
            expires = datetime.fromisoformat(record["expires"])
        except ValueError:
            continue
        if expires > _now() and (best is None or record["opened"] > best[1]["opened"]):
            best = (path, record)
    return best


def log_write(path: Path, record: dict[str, Any], tool: str) -> None:
    record.setdefault("writes", []).append({"tool": tool, "at": _now().isoformat()})
    _write(path, record)


# --- questions shown to the user (approval by click) ------------------------------------------


def mark_asked(repo: Path, name: str) -> None:
    _write(
        state_dir(repo) / "asked" / f"{safe_name(name)}.json",
        {"asked": _now().isoformat()},
    )


def take_asked(repo: Path, name: str) -> bool:
    """Whether the question-check hook let this question through; the mark is used up."""
    path = state_dir(repo) / "asked" / f"{safe_name(name)}.json"
    try:
        path.unlink()
    except OSError:
        return False
    return True


# --- manual checks (guarded-paths) ------------------------------------------------------------


def record_manual(repo: Path, name: str, tree: str, note: str) -> None:
    _write(
        state_dir(repo) / "manual" / f"{safe_name(name)}-{tree}.json",
        {"name": name, "tree": tree, "note": note, "recorded": _now().isoformat()},
    )


def has_manual(repo: Path, name: str, tree: str) -> bool:
    record = _read(state_dir(repo) / "manual" / f"{safe_name(name)}-{tree}.json")
    return bool(record) and record.get("tree") == tree and record.get("name") == name


# --- check evidence (guarded-paths, draft-reviewed-prs) ---------------------------------------


def record_checks(repo: Path, tree: str, results: list[dict[str, Any]]) -> Path:
    path = state_dir(repo) / "checks" / f"{tree}.json"
    _write(path, {"tree": tree, "recorded": _now().isoformat(), "results": results})
    return path


def passed_checks(repo: Path, tree: str) -> set[str]:
    record = _read(state_dir(repo) / "checks" / f"{tree}.json")
    if not record:
        return set()
    return {r["name"] for r in record.get("results", []) if r.get("exit_code") == 0}


# --- review verdicts (draft-reviewed-prs) -----------------------------------------------------


def record_review(repo: Path, head: str, verdict: str, summary: str) -> Path:
    if verdict not in {"ready", "blocked"}:
        raise ValueError("verdict must be 'ready' or 'blocked'")
    path = state_dir(repo) / "review" / f"{head}.json"
    _write(
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
    record = _read(state_dir(repo) / "review" / f"{head}.json")
    return record.get("verdict") if record else None
