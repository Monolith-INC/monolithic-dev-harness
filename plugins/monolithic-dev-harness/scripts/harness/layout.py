"""Where the harness keeps its files in a repository, and how older layouts move into it.

Everything lives under one folder (ADR-0008):

    .harness/
      policy.json            the rules (human-owned)
      integrations.json      tracker and repository connection
      review/                where review requirements live, and the review knowledge store
      backlog/               backlog settings, estimation, reports
      tracker/               local tracker records, when that tracker is used
      state/                 approvals, manual checks, evidence, scratch (not committed)
        prompts/             orchestrator prompt mailbox
        backups/             work-item backups taken before an amendment

Before 0.1.6 these were spread over one folder per source plugin. `migrate` moves them in; it is the
only code that knows the old names besides the read fallbacks, which keep an unmigrated repository
working until bootstrap runs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HARNESS = ".harness"
INTEGRATIONS = f"{HARNESS}/integrations.json"
REVIEW = f"{HARNESS}/review"
BACKLOG = f"{HARNESS}/backlog"
TRACKER = f"{HARNESS}/tracker"
STATE = f"{HARNESS}/state"
PROMPTS = f"{STATE}/prompts"
BACKUPS = f"{STATE}/backups"

# (old location, new location), in the order they are moved.
_MOVES = (
    (".codex-workflows/integrations.json", INTEGRATIONS),
    (".monolithic-code-review", REVIEW),
    (".agile-backlog-toolkit", BACKLOG),
    (".agile-backlog-toolkit.install.json", f"{BACKLOG}/install.json"),
    (".local-tracker", TRACKER),
    (".agentic/workflow_prompts", PROMPTS),
    (".agentic/backups", BACKUPS),
)
# Old folders removed once the moves leave nothing but what the harness no longer uses.
_OLD_FOLDERS = (".codex-workflows", ".agentic")
# Leftovers of the old layout that nothing reads any more.
_STALE = (".codex-workflows/active-stage", ".agentic/workflow_prompts/.gitkeep")


def migrate(repo: Path) -> list[str]:
    """Move an older layout into `.harness/`. Returns one line per thing done or left alone.

    Nothing is overwritten: when both the old and the new location exist, the old one is kept and
    reported, for a person to merge.
    """
    notes: list[str] = []
    for old, new in _MOVES:
        source, target = repo / old, repo / new
        if not source.exists():
            continue
        if target.exists():
            notes.append(f"kept {old}: {new} already exists; merge them by hand")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        notes.append(f"moved {old} to {new}")
        if new == TRACKER:
            notes.extend(_repoint_tracker(repo))
    for stale in _STALE:
        path = repo / stale
        if path.is_file():
            path.unlink()
    for folder in _OLD_FOLDERS:
        path = repo / folder
        if path.is_dir():
            if any(path.iterdir()):
                notes.append(
                    f"kept {folder}/: it still holds files the harness does not use"
                )
            else:
                path.rmdir()
                notes.append(f"removed the empty {folder}/")
    return notes


def _repoint_tracker(repo: Path) -> list[str]:
    """The local tracker's folder is recorded in the integrations file; follow the move."""
    path = repo / INTEGRATIONS
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    tracker = payload.get("tracker") if isinstance(payload, dict) else None
    if not isinstance(tracker, dict) or tracker.get("root") in (None, TRACKER):
        return []
    tracker["root"] = TRACKER
    connection = tracker.get("connection")
    if isinstance(connection, dict) and isinstance(connection.get("args"), list):
        connection["args"] = [
            TRACKER if arg == ".local-tracker" else arg for arg in connection["args"]
        ]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return [f"pointed the local tracker at {TRACKER}"]
