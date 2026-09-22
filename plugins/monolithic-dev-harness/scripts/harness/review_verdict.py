#!/usr/bin/env python3
"""Record the review stage's verdict for the current HEAD commit.

    review_verdict.py --verdict ready|blocked --summary "<one line>" [--repo <dir>]

The verdict is keyed to HEAD's commit id, so any new commit invalidates it and the PR gate (draft-reviewed-prs)
asks for a fresh review. `ready` requires a clean working tree: the review must describe exactly
what the pull request will contain.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import gitstate, state  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--verdict", choices=("ready", "blocked"), required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args(argv)

    repo = gitstate.repo_root(Path(args.repo)) or Path(args.repo).resolve()
    if args.verdict == "ready" and gitstate.git(repo, "status", "--porcelain", "--untracked-files=no"):
        print("working tree has uncommitted changes; commit (and re-review) before recording `ready`", file=sys.stderr)
        return 2
    head = gitstate.head_sha(repo)
    path = state.record_review(repo, head, args.verdict, args.summary)
    print(f"review verdict `{args.verdict}` recorded for {head[:12]}: {path.relative_to(repo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
