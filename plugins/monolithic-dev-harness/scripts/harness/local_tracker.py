"""Storage layout for the bundled local work tracker.

The tracker adapter creates records on demand. Bootstrap creates its complete directory layout so
an empty tracker is visibly ready before any planning or implementation begins.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.result import Result, attempt
from harness import gitstate, state
from integrations.contracts import Manifest

ROOT = Path(".harness/tracker")
SUPPORT_FOLDERS = ("artifacts", "capacity")


def storage_root(repo: Path) -> Path:
    """Use one tracker store for every linked worktree of a clone."""
    try:
        common = Path(
            gitstate.git(
                repo, "rev-parse", "--path-format=absolute", "--git-common-dir"
            )
        )
    except gitstate.GitError:
        return repo / ROOT
    return (common.parent if common.name == ".git" else repo) / ROOT


def folders(manifest: Manifest) -> tuple[str, ...]:
    return (*dict.fromkeys(manifest.states.values()), *SUPPORT_FOLDERS)


def describe(repo: Path, manifest: Manifest) -> dict[str, object]:
    root = storage_root(repo)
    expected = folders(manifest)
    return {
        "path": str(root),
        "ready": all((root / name).is_dir() for name in expected),
        "folders": list(expected),
        "work_item_count": sum(
            len(tuple((root / state).glob("*.json")))
            for state in dict.fromkeys(manifest.states.values())
        ),
    }


def prepare(repo: Path, manifest: Manifest) -> Result[dict[str, object]]:
    def create() -> dict[str, object]:
        state.ensure_local_exclude(repo)
        root = storage_root(repo)
        for name in folders(manifest):
            (root / name).mkdir(parents=True, exist_ok=True)
        return describe(repo, manifest)

    return attempt(
        create,
        "local_tracker_unwritable",
        f"could not prepare local tracker at {storage_root(repo)}",
        OSError,
        subprocess.TimeoutExpired,
    )
