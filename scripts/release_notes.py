#!/usr/bin/env python3
"""Print the CHANGELOG.md section for one version (used as the GitHub release notes).

release_notes.py vX.Y.Z
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    version = sys.argv[1].removeprefix("v")
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)",
        text,
        re.M | re.S,
    )
    if not match or not match.group(1).strip():
        print(f"CHANGELOG.md has no section for {version}", file=sys.stderr)
        return 1
    print(match.group(1).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
