"""Validate and install a user-supplied tracker manifest pending explicit approval.

PYTHONPATH="<plugin root>/scripts" python3 -m trackers.onboarding stage <folder> [--repo <dir>]
PYTHONPATH="<plugin root>/scripts" python3 -m trackers.onboarding approve <name> [--repo <dir>]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .registry import NAME, TrackerError, validate_manifest


def stage(repo: Path, source: Path) -> Path:
    """Copy one manifest folder into the human-reviewable onboarding area."""
    manifest_path = source / "tracker.json"
    try:
        manifest = validate_manifest(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, TrackerError) as exc:
        raise TrackerError(f"tracker onboarding failed: {exc}") from exc
    destination = repo / ".harness" / "trackers" / str(manifest["name"])
    if destination.exists():
        raise TrackerError(
            f"tracker onboarding destination already exists: {destination}"
        )
    shutil.copytree(source, destination)
    payload: dict[str, Any] = json.loads(
        (destination / "tracker.json").read_text(encoding="utf-8")
    )
    (destination / "tracker.json").write_text(
        json.dumps({**payload, "status": "draft"}, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def approve(repo: Path, name: str) -> Path:
    """Mark a staged manifest ready for an approval that names the tracker to pin it."""
    if not NAME.fullmatch(name):
        raise TrackerError(f"tracker approval failed: {name!r} is not a tracker name")
    path = repo / ".harness" / "trackers" / name / "tracker.json"
    try:
        manifest = validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TrackerError) as exc:
        raise TrackerError(f"tracker approval failed: {exc}") from exc
    path.write_text(
        json.dumps({**manifest, "status": "approved"}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m trackers.onboarding")
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage", help="copy a tracker folder in as a draft")
    staging.add_argument("source", type=Path)
    approving = commands.add_parser("approve", help="mark a staged tracker approved")
    approving.add_argument("name")
    for command in (staging, approving):
        command.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        path = (
            stage(args.repo, args.source)
            if args.command == "stage"
            else approve(args.repo, args.name)
        )
    except TrackerError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
