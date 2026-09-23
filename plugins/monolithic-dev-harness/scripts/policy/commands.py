"""The workflow policy reads shell commands through the harness's shared reader (`shellscan`).

One reader for every rule: a separate, simpler parser here used to see only the first `git` on a
line, and counted any `>` (even `2>/dev/null`) as a file write.
"""

from __future__ import annotations

from pathlib import Path

try:
    from harness import shellscan
except ImportError:  # imported as `scripts.policy`, as the tests do
    from scripts.harness import shellscan


def git_commands(command: str) -> list[list[str]]:
    """The argv (after git's own options) of every `git` the command runs."""
    return [argv for _directory, argv in shellscan.git_commands(command)]


def writes_inside(command: str, root: str | Path | None) -> bool:
    """Whether the command could write a file inside the repository."""
    return shellscan.writes_inside(command, Path(root) if root else None)
