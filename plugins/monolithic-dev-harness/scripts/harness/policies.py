"""Repository-local suspension of harness checks, on the human's request.

Suspension releases every harness check except the protection of human-owned records, and leaves
the settings, tracker, sessions, and evidence as they are. `.harness/state/policies.json` holds
the mode and changes only through `harness policies suspend|resume`.
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from core.result import Result, attempt
from harness import gitstate, state

RELATIVE_PATH = Path(".harness/state/policies.json")
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = ("suspend", "resume", "status")


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
    """Whether `command` is exactly this plugin's `harness policies` command for `repo`.

    The hook lets it through before loading settings, so a repository whose settings are broken
    can still be released. The executable must be this plugin's own `bin/harness` or the
    `harness` the installer linked onto the shell path; both live outside the repository.
    """
    try:
        args = shlex.split(command)
    except ValueError:
        return False
    start = Path(cwd or repo)
    match args:
        case [executable, "policies", operation] if operation in OPERATIONS:
            target = start
        case [executable, "policies", operation, "--repo", value] if (
            operation in OPERATIONS
        ):
            target = Path(value) if Path(value).is_absolute() else start / value
        case _:
            return False
    return _trusted_executable(executable, start) and _same_repo(target, repo)


def _trusted_executable(executable: str, start: Path) -> bool:
    found = shutil.which(executable) if "/" not in executable else None
    resolved = (
        Path(found) if found else start / executable if "/" in executable else None
    )
    if resolved is None or not resolved.is_file():
        return False
    resolved = resolved.resolve()
    linked = shutil.which("harness")
    return resolved == (PLUGIN_ROOT / "bin/harness").resolve() or (
        linked is not None
        and resolved == Path(linked).resolve()
        and resolved.parent.name == "bin"
        and (resolved.parents[1] / "scripts/harness/policies.py").is_file()
    )


def _same_repo(target: Path, repo: Path) -> bool:
    root = gitstate.repo_root(target) or target
    return root.resolve() == repo.resolve()
