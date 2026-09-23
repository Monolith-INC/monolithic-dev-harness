from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import IntegrationError

CONFIG_RELATIVE_PATH = ".codex-workflows/integrations.json"


@dataclass(frozen=True)
class IntegrationConfig:
    schema_version: int
    tracker: dict[str, Any]
    scm: dict[str, Any]
    branch_template: str
    project_root: Path

    @property
    def tracking_mode(self) -> str:
        return str(self.tracker.get("trackingMode") or "enforced")

    @property
    def tracking_enabled(self) -> bool:
        return self.tracking_mode == "enforced"

    @property
    def configured(self) -> bool:
        return bool(self.tracker.get("adapter")) and bool(self.scm.get("adapter"))


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_RELATIVE_PATH


def load_config(project_root: Path | None = None) -> IntegrationConfig:
    root = (project_root or _discover_project_root()).resolve()
    explicit = os.environ.get("CODEX_WORKFLOWS_CONFIG", "").strip()
    path = Path(explicit).expanduser() if explicit else config_path(root)
    if not path.is_file():
        raise IntegrationError(
            "not_configured",
            f"Integration setup is missing at {path}. Run bootstrap with a tracker and SCM selection.",
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationError(
            "invalid_config", f"Could not read integration configuration: {exc}"
        ) from exc
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 1:
        raise IntegrationError(
            "invalid_config", "Integration configuration must declare schemaVersion 1."
        )
    tracker = raw.get("tracker")
    scm = raw.get("scm")
    branch_template = raw.get("branchTemplate")
    if not isinstance(tracker, dict) or not tracker.get("adapter"):
        raise IntegrationError("invalid_config", "tracker.adapter is required.")
    if not isinstance(scm, dict) or not scm.get("adapter"):
        raise IntegrationError("invalid_config", "scm.adapter is required.")
    if not isinstance(branch_template, str) or "{key}" not in branch_template:
        raise IntegrationError(
            "invalid_config", "branchTemplate must be a string containing {key}."
        )
    if "branchPattern" not in tracker:
        tracker = {**tracker, "branchPattern": branch_template}
    tracker = {**tracker, "projectRoot": str(root)}
    tracking = raw.get("tracking")
    if isinstance(tracking, dict) and tracking.get("mode") in {"enforced", "skipped"}:
        tracker = {**tracker, "trackingMode": str(tracking["mode"])}
    return IntegrationConfig(1, tracker, scm, branch_template, root)


def write_config(project_root: Path, payload: dict[str, Any]) -> Path:
    if payload.get("schemaVersion") != 1:
        raise ValueError("configuration schemaVersion must be 1")
    path = config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def set_tracking_mode(project_root: Path, mode: str) -> IntegrationConfig:
    if mode not in {"enforced", "skipped"}:
        raise ValueError("tracking mode must be 'enforced' or 'skipped'")
    path = config_path(project_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationError(
            "invalid_config", f"Could not read integration configuration: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise IntegrationError(
            "invalid_config", "Integration configuration must be a JSON object."
        )
    payload["tracking"] = {"mode": mode}
    write_config(project_root, payload)
    return load_config(project_root)


def _discover_project_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current
