#!/usr/bin/env python3
"""Run the repository's configured checks and record evidence keyed to a git tree.

    checks.py [--repo <dir>] [--staged | --head] [--only <name> ...]

--head (default) runs against the committed HEAD and records evidence for HEAD's tree; the working
tree must be clean so the result describes exactly what was committed. --staged records evidence for
the index tree only when the working files are byte-for-byte the same tree; this fail-closed rule
prevents checks run against unstaged content from proving a different staged version.
Checks come from `.harness/settings.json` → `checks: [{name, run, when}]`; `when` globs select the
checks that apply to the files changed on the branch.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.result import Err  # noqa: E402
from harness import gitstate, settings, state  # noqa: E402
from harness.rules import applicable_checks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", default=".")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--head", action="store_true")
    mode.add_argument("--staged", action="store_true")
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per check")
    args = parser.parse_args(argv)

    repo = gitstate.repo_root(Path(args.repo)) or Path(args.repo).resolve()
    loaded = settings.load(repo)
    if isinstance(loaded, Err):
        print(f"cannot run checks: {loaded.failure.message}", file=sys.stderr)
        return 2
    chosen = loaded.value
    if args.staged:
        try:
            tree = gitstate.index_tree(repo)
            worktree = gitstate.worktree_tree(repo)
        except gitstate.GitError as exc:
            print(f"cannot compare staged and working files: {exc}", file=sys.stderr)
            return 2
        if tree != worktree:
            print(
                "staged and working files differ; checks would not prove the staged tree. "
                "Use a clean worktree whose files exactly match the index.",
                file=sys.stderr,
            )
            return 2
        changed = gitstate.staged_paths(repo)
    else:
        if gitstate.git(repo, "status", "--porcelain", "--untracked-files=no"):
            print(
                "working tree has uncommitted changes; commit them or use --staged",
                file=sys.stderr,
            )
            return 2
        tree = gitstate.head_tree(repo)
        changed = gitstate.branch_paths(repo, chosen.base_branch)

    applicable = applicable_checks(repo, chosen, changed)
    selected = [
        check
        for check in chosen.checks
        if check.name in applicable and (args.only is None or check.name in args.only)
    ]
    if not selected:
        print("no configured checks apply to the changed files")
        state.record_checks(repo, tree, [])
        return 0

    results = []
    for check in selected:
        started = time.monotonic()
        print(f"--- {check.name}: {check.run}", flush=True)
        try:
            proc = subprocess.run(check.run, shell=True, cwd=repo, timeout=args.timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 124
        results.append(
            {
                "name": check.name,
                "run": check.run,
                "exit_code": code,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
        print(f"--- {check.name}: exit {code}", flush=True)

    path = state.record_checks(repo, tree, results)
    failed = [r["name"] for r in results if r["exit_code"] != 0]
    print(f"evidence: {path.relative_to(repo)} (tree {tree[:12]})")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
