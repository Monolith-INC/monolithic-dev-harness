"""Load the per-repository harness policy (`.harness/policy.json`)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

POLICY_RELATIVE_PATH = Path(".harness") / "policy.json"

DEFAULT_POLICY: dict[str, Any] = {
    "schemaVersion": 1,
    "azure": {
        "organization": "",
        "project": "",
        "team": "",
        "repository": "",
        "protected_work_items": [],
    },
    "backlog": {"artifacts_path": ""},
    "git": {"base_branch": "develop"},
    "approvals": {"window_minutes": 20},
    "checks": [],
    "tests_required": [],
    "generated": [],
    "guarded_paths": [],
    "pull_requests": {"require_draft": True, "require_review_verdict": True},
}


class PolicyError(ValueError):
    """The repository's policy file exists but cannot be used."""


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_policy(repo_root: Path) -> dict[str, Any]:
    path = repo_root / POLICY_RELATIVE_PATH
    if not path.is_file():
        return copy.deepcopy(DEFAULT_POLICY)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"{POLICY_RELATIVE_PATH} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise PolicyError(
            f"{POLICY_RELATIVE_PATH} must be an object with schemaVersion 1"
        )
    policy = _merge(DEFAULT_POLICY, payload)
    check_names = {check.get("name") for check in policy.get("checks", [])}
    for guard in policy.get("guarded_paths", []):
        kind, _, name = str(guard.get("evidence", "")).partition(":")
        if kind not in {"check", "manual"} or not name:
            raise PolicyError(
                f"guarded path {guard.get('path')!r}: evidence must be "
                "check:<name> or manual:<name>"
            )
        if kind == "check" and name not in check_names:
            raise PolicyError(
                f"guarded path {guard.get('path')!r} needs check {name!r}, "
                "which is not in checks"
            )
    return policy


def protected_ids(policy: dict[str, Any]) -> set[str]:
    """Protected tracker references, accepting the legacy Azure policy field."""
    values = policy.get("trackers", {}).get("protected_work_items", []) or policy.get(
        "azure", {}
    ).get("protected_work_items", [])
    return {
        str(value)
        for value in values
        if isinstance(value, (str, int)) and not isinstance(value, bool)
    }
