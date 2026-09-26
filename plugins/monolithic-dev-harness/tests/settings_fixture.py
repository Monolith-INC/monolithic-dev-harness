"""One settings file for tests: the smallest valid `.harness/settings.json`, and a writer for it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MINIMAL: dict[str, Any] = {
    "schemaVersion": 1,
    "tracker": {"name": "local"},
    "scm": {"name": "github", "values": {"owner": "o", "repo": "r"}},
    "branch_template": "feature/{key}-{slug}",
}


def write_settings(repo: Path, **changes: Any) -> Path:
    path = repo / ".harness" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**MINIMAL, **changes}), encoding="utf-8")
    return path
