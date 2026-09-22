from __future__ import annotations

import subprocess
from contextlib import suppress


def _run_git_cmd(args: list[str], cwd: str, timeout: float | None = None) -> str:
    """Helper to run a git command and return its stdout, stripped."""
    try:
        res = subprocess.run(
            args, capture_output=True, text=True, cwd=cwd, timeout=timeout, check=True
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def get_integration_branch(workspace_root: str) -> str:
    """Dynamically resolves the default/base integration branch name (e.g. 'unstable' or 'develop')."""
    # 1. Try resolving refs/remotes/origin/HEAD
    ref = _run_git_cmd(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"], workspace_root
    )
    if ref:
        # e.g., 'refs/remotes/origin/unstable' -> 'unstable'
        parts = ref.split("/")
        if len(parts) > 3:
            return parts[-1]

    # 2. Try remote show origin
    show_output = _run_git_cmd(
        ["git", "remote", "show", "origin"], workspace_root, timeout=3.0
    )
    for line in show_output.splitlines():
        if "HEAD branch:" in line:
            return line.split("HEAD branch:", 1)[1].strip()

    # 3. Scan remote branches for known names in order of preference
    branch_output = _run_git_cmd(["git", "branch", "-r"], workspace_root)
    branches = {
        line.strip().replace("origin/", "")
        for line in branch_output.splitlines()
        if line
    }
    for preferred in ["unstable", "develop", "main", "master"]:
        if preferred in branches:
            return preferred

    # 4. Scanning local branches as a last resort
    local_output = _run_git_cmd(["git", "branch"], workspace_root)
    local_branches = {
        line.strip().replace("* ", "") for line in local_output.splitlines() if line
    }
    for preferred in ["unstable", "develop", "main", "master"]:
        if preferred in local_branches:
            return preferred

    # Default fallback
    return "develop"


def run_git_fetch(workspace_root: str, base_branch: str) -> None:
    """Runs git fetch origin for the base branch with a short timeout to get remote state."""
    # We do a fast fetch. Timeout is 2.0s to prevent hanging hook.
    with suppress(Exception):
        subprocess.run(
            ["git", "fetch", "origin", base_branch],
            capture_output=True,
            cwd=workspace_root,
            timeout=2.0,
            check=False,
        )


def get_commits_behind_base(workspace_root: str, base_branch: str) -> list[str]:
    """Gets commits that are in origin/base_branch but not in the current HEAD."""
    output = _run_git_cmd(
        ["git", "log", f"HEAD..origin/{base_branch}", "--format=%H"], workspace_root
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_unmerged_commits_intersection(
    workspace_root: str, base_branch: str
) -> dict[str, list[str]]:
    """Find if the current HEAD contains unmerged commits from other local work branches.

    Returns:
        A dictionary mapping other_branch -> list of overlapping unmerged commit hashes.
    """
    current_branch = _run_git_cmd(["git", "branch", "--show-current"], workspace_root)
    if not current_branch:
        return {}

    # Get commits in HEAD that are not in origin/base_branch
    head_unmerged_output = _run_git_cmd(
        ["git", "log", f"origin/{base_branch}..HEAD", "--format=%H"], workspace_root
    )
    head_unmerged = {
        line.strip() for line in head_unmerged_output.splitlines() if line.strip()
    }
    if not head_unmerged:
        return {}

    # Inspect all local work branches; naming is configured during bootstrap.
    all_refs = _run_git_cmd(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        workspace_root,
    )
    other_branches = []
    for line in all_refs.splitlines():
        branch = line.strip()
        if not branch or branch == current_branch:
            continue
        if branch not in {"main", "master", "develop", "unstable"}:
            other_branches.append(branch)

    intersection_map = {}
    for other in other_branches:
        # Check if other branch has unmerged commits
        other_unmerged_output = _run_git_cmd(
            ["git", "log", f"origin/{base_branch}..{other}", "--format=%H"],
            workspace_root,
        )
        other_unmerged = {
            line.strip() for line in other_unmerged_output.splitlines() if line.strip()
        }
        if not other_unmerged:
            continue

        overlap = head_unmerged.intersection(other_unmerged)
        if overlap:
            intersection_map[other] = sorted(list(overlap))

    return intersection_map
