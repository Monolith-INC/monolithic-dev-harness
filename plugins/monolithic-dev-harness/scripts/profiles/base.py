"""Optional workspace defaults for installer discovery.

Durable work state and provider details are loaded from integrations.json;
profiles only provide local verification and protected-branch defaults.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceProfile:
    name: str
    project_name: str
    tracker_name: str
    branch_name: str
    verify_command: str


def _generic_profile() -> WorkspaceProfile:
    return WorkspaceProfile(
        "generic", "project", "configured", "main", "python3 -m unittest"
    )


def _flutter_profile() -> WorkspaceProfile:
    return WorkspaceProfile(
        "flutter", "project", "configured", "develop", "flutter test"
    )


def _repository_profile() -> WorkspaceProfile:
    return WorkspaceProfile(
        "repository", "project", "configured", "main", "python3 -m unittest"
    )


_PROFILE_FACTORIES: dict[str, Callable[[], WorkspaceProfile]] = {
    "generic": _generic_profile,
    "flutter": _flutter_profile,
    "repository": _repository_profile,
}


def load_profile(name: str) -> WorkspaceProfile:
    try:
        return _PROFILE_FACTORIES[name]()
    except KeyError as error:
        raise ValueError(f"Unknown profile: {name}") from error
