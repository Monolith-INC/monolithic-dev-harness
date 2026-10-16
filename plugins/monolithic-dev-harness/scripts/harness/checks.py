#!/usr/bin/env python3
"""Run the repository's configured checks and record evidence for the code as it is now.

    checks.py [--repo <dir>] [--session-id <id>] [--only <name> ...]

Evidence is keyed to the digest of the project's code files (`harness.code_content`), so it
describes exactly the code on disk; any later change to a code file needs a new run. Version
control plays no part. Checks come from `.harness/settings.json` → `checks: [{name, run, when}]`;
`when` globs select the checks that apply to the files changed since the work session linked its
work item (all code files when that is unknown). A check that changes code files records nothing:
its result would describe code that no longer exists.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.result import Err  # noqa: E402
from harness import (  # noqa: E402
    code_content,
    project_paths,
    settings,
    state,
    work_sessions,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--session-id", help="the work session (default: the current one)"
    )
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per check")
    args = parser.parse_args(argv)

    repo = project_paths.root(Path(args.repo))
    loaded = settings.load(repo)
    if isinstance(loaded, Err):
        print(f"cannot run checks: {loaded.failure.message}", file=sys.stderr)
        return 2
    chosen = loaded.value
    before = code_content.files(repo)
    digest = code_content.digest(before)
    changed = code_content.changed_since_link(
        repo, args.session_id or work_sessions.current(repo), before
    )

    applicable = code_content.applicable_checks(chosen, changed)
    selected = [
        check
        for check in chosen.checks
        if check.name in applicable and (args.only is None or check.name in args.only)
    ]
    if not selected:
        print("no configured checks apply to the changed files")
        state.record_checks(repo, digest, [])
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

    if code_content.digest(code_content.files(repo)) != digest:
        print(
            "the checks changed code files, so their results describe code that is gone; "
            "nothing was recorded. Review the changes and run the checks again.",
            file=sys.stderr,
        )
        return 2
    path = state.record_checks(repo, digest, results)
    failed = [r["name"] for r in results if r["exit_code"] != 0]
    print(f"evidence: {path.relative_to(repo)} (code {digest[:12]})")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
