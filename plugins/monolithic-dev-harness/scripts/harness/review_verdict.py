#!/usr/bin/env python3
"""Record the review stage's verdict for the code as it is now.

    review_verdict.py --verdict ready|blocked --summary "<one line>" [--repo <dir>]

The verdict is keyed to the digest of the project's code files (`harness.code_content`), so any
later change to a code file invalidates it and the completion and pull-request checks ask for a
fresh review. Version control plays no part.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import code_content, project_paths, state  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--verdict", choices=("ready", "blocked"), required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args(argv)

    repo = project_paths.root(Path(args.repo))
    digest = code_content.current(repo)
    path = state.record_review(repo, digest, args.verdict, args.summary)
    print(
        f"review verdict `{args.verdict}` recorded for code {digest[:12]}: "
        f"{path.relative_to(repo)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
