"""Per-project configuration for the backlog stage, read from the repository's settings.

The one source is `.harness/settings.json` (see `scripts/harness/settings.py`): the artifacts path
and the selected tracker's values. This module only reads it; people edit the file.

`artifacts_path` has **no default**. When it is unset, filesystem output is unavailable and the
caller must ask for a path rather than inventing one. Nothing here raises: missing values are
reported by `missing()`, never guessed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from core.result import Ok  # noqa: E402
from harness import settings  # noqa: E402

PLUGIN_DIRNAME = ".harness/backlog"


@dataclass(frozen=True)
class AzureConfig:
    org: str | None = None
    project: str | None = None
    team: str | None = None
    process: str | None = None
    """agile | scrum | cmmi -- decides whether Original Estimate exists on this project."""

    def as_dict(self) -> dict[str, str]:
        pairs = (
            ("org", self.org),
            ("project", self.project),
            ("team", self.team),
            ("process", self.process),
        )
        return {k: v for k, v in pairs if v}


@dataclass(frozen=True)
class LinearConfig:
    team: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {"team": self.team} if self.team else {}


@dataclass(frozen=True)
class ProjectConfig:
    artifacts_path: str | None = None
    """Where the user wants local artifacts written. No default -- ask, never assume."""

    azure: AzureConfig = AzureConfig()
    linear: LinearConfig = LinearConfig()
    provider_mode: str = "local"
    sources: tuple[str, ...] = ()

    REQUIRED_AZURE = ("org", "project")
    """Team is optional: most calls work without it, and a project has a default team."""

    def missing(self, *, require_team: bool = False) -> list[str]:
        needed = list(self.REQUIRED_AZURE) + (["team"] if require_team else [])
        return [key for key in needed if not getattr(self.azure, key)]

    @property
    def azure_ready(self) -> bool:
        return not self.missing()

    @property
    def artifacts_ready(self) -> bool:
        return bool(self.artifacts_path)

    def resolve_artifacts_dir(self, project_root: Path) -> Path | None:
        """Absolute artifacts directory, or None when the user has not named one.

        An absolute configured path is used as given; a relative one is taken from the
        project root. The directory is not created here -- callers create only what they
        are about to write into, and only under a path the user chose.
        """
        if not self.artifacts_path:
            return None
        candidate = Path(self.artifacts_path).expanduser()
        return candidate if candidate.is_absolute() else Path(project_root) / candidate

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.artifacts_path:
            payload["artifacts_path"] = self.artifacts_path
        azure = self.azure.as_dict()
        if azure:
            payload["azure"] = azure
        linear = self.linear.as_dict()
        if linear:
            payload["linear"] = linear
        payload["provider_mode"] = self.provider_mode
        return payload


def plugin_dir(project_root: Path) -> Path:
    """`.harness/backlog/`: where the backlog stage keeps its own reports and records.

    Distinct from the artifacts path: this holds plugin internals, never the user's work products.
    """
    return Path(project_root) / PLUGIN_DIRNAME


def project_root_of(state_dir: Path) -> Path:
    """The project a plugin state directory belongs to (inverse of `plugin_dir`)."""
    return Path(state_dir).parents[len(Path(PLUGIN_DIRNAME).parts) - 1]


def _value(values: Any, key: str) -> str | None:
    text = str(values.get(key, "")).strip()
    return text or None


def load_project_config(project_root: Path) -> ProjectConfig:
    """The backlog view of the repository's settings; empty when the settings cannot be read."""
    match settings.load(Path(project_root)):
        case Ok(chosen):
            values = chosen.tracker.values
            azure = chosen.tracker.name == "azure-devops"
            return ProjectConfig(
                artifacts_path=chosen.artifacts_path or None,
                azure=AzureConfig(
                    org=_value(values, "organization"),
                    project=_value(values, "project"),
                    team=_value(values, "team"),
                    process=_value(values, "process"),
                )
                if azure
                else AzureConfig(),
                linear=LinearConfig(team=_value(values, "team"))
                if chosen.tracker.name == "linear"
                else LinearConfig(),
                provider_mode=chosen.tracker.name,
                sources=(str(settings.SETTINGS_RELATIVE_PATH),),
            )
        case _:
            return ProjectConfig()
