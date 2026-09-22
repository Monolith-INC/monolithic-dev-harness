"""Read-only git queries the rules need. Every call is bounded by a timeout."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 4


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env={**os.environ, **(env or {})},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError(f"git {' '.join(args)} failed: {exc}") from exc
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


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
