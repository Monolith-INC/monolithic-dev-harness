"""Per-project configuration for the backlog stage, read from the repository's settings.

The one source is `.harness/settings.json` (see `scripts/harness/settings.py`): the artifacts path
and which tracker is selected. The tracker's own values are the registry's to read and check.
This module only reads the file; people edit it.

`artifacts_path` has **no default**. When it is unset, filesystem output is unavailable and the
caller must ask for a path rather than inventing one. Nothing here raises: missing values are
reported by `missing()`, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.result import Ok, Result
from harness import settings
from harness.settings import Settings

PLUGIN_DIRNAME = ".harness/backlog"


@dataclass(frozen=True)
class ProjectConfig:
    artifacts_path: str | None = None
    """Where the user wants local artifacts written. No default -- ask, never assume."""

    tracker: str = ""
    """The selected tracker's name. Its values and problems come from the registry, not here."""

    sources: tuple[str, ...] = ()

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


def plugin_dir(project_root: Path) -> Path:
    """`.harness/backlog/`: where the backlog stage keeps its own reports and records.

    Distinct from the artifacts path: this holds plugin internals, never the user's work products.
    """
    return Path(project_root) / PLUGIN_DIRNAME


def project_root_of(state_dir: Path) -> Path:
    """The project a plugin state directory belongs to (inverse of `plugin_dir`)."""
    return Path(state_dir).parents[len(Path(PLUGIN_DIRNAME).parts) - 1]


def load_project_config(project_root: Path) -> ProjectConfig:
    """The backlog view of the repository's settings; empty when the settings cannot be read."""
    return from_settings(settings.load(Path(project_root)))


def from_settings(loaded: Result[Settings]) -> ProjectConfig:
    match loaded:
        case Ok(chosen):
            return ProjectConfig(
                artifacts_path=chosen.artifacts_path or None,
                tracker=chosen.tracker.name,
                sources=(str(settings.SETTINGS_RELATIVE_PATH),),
            )
        case _:
            return ProjectConfig()
