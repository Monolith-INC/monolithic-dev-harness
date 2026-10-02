"""Git queries the rules need, over one bounded runner. Every call has a timeout."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 4


class GitError(RuntimeError):
    pass


def run(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    input_bytes: bytes | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> bytes:
    """Raw stdout of one git command; any failure is a `GitError`."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args)} failed: {exc}") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return run(repo, *args, env=env).decode(errors="replace").strip()


def repo_root(start: Path) -> Path | None:
    try:
        return Path(git(start, "rev-parse", "--show-toplevel"))
    except GitError:
        return None


def head_sha(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD")


def head_tree(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD^{tree}")


def index_tree(repo: Path) -> str:
    """Tree object of what `git commit` would record right now."""
    return git(repo, "write-tree")


def worktree_tree(repo: Path) -> str:
    """Tree object of the working tree (tracked + untracked, respecting .gitignore).

    Built in a throwaway index so the real index is never touched.
    """
    real_index = Path(
        git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index")
    )
    with tempfile.TemporaryDirectory(prefix="harness-index-") as tmp:
        temp_index = Path(tmp) / "index"
        if real_index.exists():
            shutil.copyfile(real_index, temp_index)
        env = {"GIT_INDEX_FILE": str(temp_index)}
        git(repo, "add", "-A", env=env)
        return git(repo, "write-tree", env=env)


def staged_paths(repo: Path, include_tracked_modifications: bool = False) -> list[str]:
    paths = set(filter(None, git(repo, "diff", "--cached", "--name-only").splitlines()))
    if include_tracked_modifications:
        paths |= set(filter(None, git(repo, "diff", "--name-only").splitlines()))
    return sorted(paths)


def branch_paths(repo: Path, base_branch: str) -> list[str]:
    """Paths changed on this branch relative to its merge-base with the base branch."""
    if not base_branch:
        return []
    for base in (f"origin/{base_branch}", base_branch):
        try:
            merge_base = git(repo, "merge-base", base, "HEAD")
        except GitError:
            continue
        return sorted(
            filter(
                None,
                git(repo, "diff", "--name-only", f"{merge_base}..HEAD").splitlines(),
            )
        )
    return []
