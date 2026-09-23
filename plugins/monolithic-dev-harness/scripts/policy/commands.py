"""The workflow policy reads shell commands through the harness's shared reader (`shellscan`).

One reader for every rule: a separate, simpler parser here used to see only the first `git` on a
line, and counted any `>` (even `2>/dev/null`) as a file write.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

try:
    from harness import globs, shellscan
except ImportError:  # imported as `scripts.policy`, as the tests do
    from scripts.harness import globs, shellscan

# Never code, whatever the policy says: git's own files and the harness's.
_NOT_CODE = (".git", ".harness")


def git_commands(command: str) -> list[list[str]]:
    """The argv (after git's own options) of every `git` the command runs."""
    return [argv for _directory, argv in shellscan.git_commands(command)]


def is_code(relative: str, patterns: Sequence[str] | None, tree: bool = False) -> bool:
    """Whether writing `relative` (repository-relative) could change code.

    `patterns` are the policy's source and test globs; `None` means the policy names none, and then
    every file but git's and the harness's counts. `tree` means the write reaches everything under
    `relative` (`rm -r`), so it counts when a code file could live under it.
    """
    parts = [part for part in globs.normalize(relative).split("/") if part not in ("", ".")]
    if parts[:1] == [".."]:
        return False
    if parts[:1] and parts[0] in _NOT_CODE:
        return False
    if patterns is None:
        return True
    path = "/".join(parts)
    if not tree:
        return globs.matches(path, patterns)
    if not path:
        return True
    for pattern in patterns:
        prefix = globs.normalize(pattern).split("*", 1)[0].split("?", 1)[0]
        if not prefix or prefix.startswith(path + "/") or path.startswith(prefix):
            return True
    return False


def writes_code(command: str, root: str | Path | None, patterns: Sequence[str] | None) -> bool:
    """Whether the command plainly writes a code file inside the repository.

    A code path named where its write cannot be followed (inline interpreter code, a script's
    arguments) counts as written.
    """
    base = Path(root).resolve() if root else None
    writes = shellscan.scan(command, "", base, unknown_writes=False)
    unresolved = writes.unresolved if patterns is not None else ()
    for paths, tree in ((writes.targets, False), (writes.trees, True), (unresolved, False)):
        for path in paths:
            relative = _inside(path, base)
            if relative is not None and is_code(relative, patterns, tree):
                return True
    return False


def _inside(path: str, base: Path | None) -> str | None:
    if not path.startswith(("/", "~")):
        return path
    if base is None:
        return None
    try:
        return Path(path).resolve().relative_to(base).as_posix()
    except ValueError:
        return None
