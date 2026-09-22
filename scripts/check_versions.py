#!/usr/bin/env python3
"""Fail unless every version source agrees (and, with --tag, matches the release tag).

    check_versions.py [--tag vX.Y.Z]

Sources: both plugin manifests, the Claude marketplace entry, the newest CHANGELOG heading, and
the README version badge.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "monolithic-dev-harness"


def sources() -> dict[str, str]:
    found = {
        "plugins/…/.claude-plugin/plugin.json": json.loads(
            (PLUGIN / ".claude-plugin/plugin.json").read_text()
        )["version"],
        "plugins/…/.cursor-plugin/plugin.json": json.loads(
            (PLUGIN / ".cursor-plugin/plugin.json").read_text()
        )["version"],
    }
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    found[".claude-plugin/marketplace.json"] = next(
        p["version"]
        for p in marketplace["plugins"]
        if p["name"] == "monolithic-dev-harness"
    )
    heading = re.search(
        r"^## \[(\d+\.\d+\.\d+)\]", (ROOT / "CHANGELOG.md").read_text(), re.M
    )
    found["CHANGELOG.md (newest release)"] = (
        heading.group(1) if heading else "<missing>"
    )
    badge = re.search(
        r"badge/version-(\d+\.\d+\.\d+)-", (ROOT / "README.md").read_text()
    )
    found["README.md (version badge)"] = badge.group(1) if badge else "<missing>"
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    args = parser.parse_args()
    found = sources()
    expected = (
        args.tag.removeprefix("v")
        if args.tag
        else found["plugins/…/.claude-plugin/plugin.json"]
    )
    mismatched = {k: v for k, v in found.items() if v != expected}
    for key, value in found.items():
        print(f"{'ok ' if value == expected else 'BAD'} {value:<10} {key}")
    if mismatched:
        print(f"versions disagree (expected {expected})", file=sys.stderr)
        return 1
    print(f"all version sources agree on {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
