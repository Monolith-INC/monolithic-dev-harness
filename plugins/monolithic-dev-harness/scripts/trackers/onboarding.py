"""Validate and install a user-supplied tracker manifest pending explicit approval."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .registry import TrackerError, validate_manifest


def stage(repo: Path, source: Path) -> Path:
    """Copy one manifest folder into the human-reviewable onboarding area."""
    manifest_path = source / "tracker.json"
    try:
        manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TrackerError) as exc:
        raise TrackerError(f"tracker onboarding failed: {exc}") from exc
    destination = repo / ".harness" / "trackers" / str(manifest["name"])
    if destination.exists():
        raise TrackerError(f"tracker onboarding destination already exists: {destination}")
    shutil.copytree(source, destination)
    payload: dict[str, Any] = json.loads((destination / "tracker.json").read_text(encoding="utf-8"))
    (destination / "tracker.json").write_text(
        json.dumps({**payload, "status": "draft"}, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def approve(repo: Path, name: str) -> Path:
    """Mark a staged manifest ready for an approval hook to pin by checksum."""
    path = repo / ".harness" / "trackers" / name / "tracker.json"
    try:
        manifest = validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TrackerError) as exc:
        raise TrackerError(f"tracker approval failed: {exc}") from exc
    path.write_text(json.dumps({**manifest, "status": "approved"}, indent=2) + "\n", encoding="utf-8")
    return path.parent
