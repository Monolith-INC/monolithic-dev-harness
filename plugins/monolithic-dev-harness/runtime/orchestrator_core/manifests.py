from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def manifest_by_name(skills_dir: Path) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    if not skills_dir.is_dir():
        return manifests
    for path in sorted(skills_dir.glob("*/manifest.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name") or path.parent.name
        manifests[name] = data
    return manifests
