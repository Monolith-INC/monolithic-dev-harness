#!/usr/bin/env python3
"""Validate the workflow plugin manifest for CI and local checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def validate_plugin(repo_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = repo_root / "codex-workflows-plugin.json"
    if not manifest_path.is_file():
        errors.append(f"Missing manifest: {manifest_path}")
        return errors

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {manifest_path}: {exc}")
        return errors

    for key in ("name", "version", "description", "skills"):
        if key not in manifest:
            errors.append(f"Manifest missing required field '{key}'")

    skills_path = manifest.get("skills")
    if isinstance(skills_path, str):
        resolved = (repo_root / skills_path).resolve()
        if not resolved.is_dir():
            errors.append(f"Skills directory not found: {resolved}")

    skills_dir = repo_root / "skills" / "codex_workflows"
    if not skills_dir.is_dir():
        errors.append(f"Missing core skill directory: {skills_dir}")

    return errors


def main() -> int:
    repo_root = (
        Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    )
    errors = validate_plugin(repo_root)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"ok: {repo_root / 'codex-workflows-plugin.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
