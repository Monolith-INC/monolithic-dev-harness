"""Repository-local suspension; independent of tracker setup and implementation sessions."""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from core.result import Result, attempt
from harness import state

RELATIVE_PATH = Path(".harness/state/policies.json")


def suspended(repo: Path) -> bool:
    return (state.read_json(repo / RELATIVE_PATH) or {}).get("mode") == "suspended"


def status(repo: Path) -> dict[str, str]:
    return {"mode": "suspended" if suspended(repo) else "active"}


def change(repo: Path, operation: str) -> Result[dict[str, str]]:
    return attempt(
        lambda: _save(repo, operation),
        "policies_unwritable",
        str(repo / RELATIVE_PATH),
        OSError,
        ValueError,
    )


def _save(repo: Path, operation: str) -> dict[str, str]:
    match operation:
        case "suspend":
            mode = "suspended"
        case "resume":
            mode = "active"
        case _:
            raise ValueError("choose suspend or resume")
    state.write_json(repo / RELATIVE_PATH, {"mode": mode})
    return {"mode": mode}


def control_command(command: str, repo: Path, cwd: str = "") -> bool:
    """Allow only this plugin's exact local control command before loading broken settings."""
    try:
        args = shlex.split(command)
    except ValueError:
        return False
    plugin = Path(__file__).resolve().parents[2]
    executable = (
        Path(shutil.which(args[0]) or str(Path(cwd or repo) / args[0])).resolve()
        if args
        else Path()
    )
    match args:
        case [_, "policies", "suspend" | "resume" | "status"]:
            return (
                executable == plugin / "bin/harness"
                and Path(cwd or repo).resolve() == repo.resolve()
            )
        case [_, "policies", "suspend" | "resume" | "status", "--repo", target]:
            destination = Path(target)
            root = (
                destination
                if destination.is_absolute()
                else Path(cwd or repo) / destination
            )
            return (
                executable == plugin / "bin/harness"
                and root.resolve() == repo.resolve()
            )
        case _:
            return False
