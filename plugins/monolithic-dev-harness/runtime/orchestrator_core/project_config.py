"""Per-project configuration: where to write artifacts, and which Azure DevOps to talk to.

Lives at `.agile-backlog-toolkit/config.json` in the project root. Written by the installer and by
lazy fill; read by the orchestrator and by skills.

**The plugin knows nothing about the client project beyond what is in this file.** It does
not create directory structures, does not search for any, and does not know or care what
lives at the artifacts path a user gives it. That path is a string the user supplied and
nothing more.

`artifacts_path` has **no default**. When it is unset, filesystem output is unavailable and
the caller must ask for a path rather than inventing one.

Values resolve from several places, earliest wins:

    1. environment variables               -- CI and one-off overrides
    2. .agile-backlog-toolkit/config.json   -- the canonical file
    3. .agile-backlog-toolkit.install.json  -- install receipt
    4. .mcp.json / .cursor/mcp.json        -- org, read from the MCP command arguments

Nothing here raises. Missing values are reported by `missing()`, never guessed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

PLUGIN_DIRNAME = ".agile-backlog-toolkit"
CONFIG_RELPATH = Path(PLUGIN_DIRNAME) / "config.json"
INSTALL_MANIFEST = ".agile-backlog-toolkit.install.json"
MCP_FILES = (Path(".mcp.json"), Path(".cursor") / "mcp.json")

ENV_ARTIFACTS = ("AGILE_WORKFLOW_ARTIFACTS_PATH", "AGILE_WORKFLOW_ARTIFACTS")
ENV_ORG = ("AGILE_WORKFLOW_AZURE_ORG", "AZURE_DEVOPS_ORG", "ADO_ORG")
ENV_PROJECT = ("AGILE_WORKFLOW_AZURE_PROJECT", "AZURE_DEVOPS_PROJECT", "ADO_PROJECT")
ENV_TEAM = ("AGILE_WORKFLOW_AZURE_TEAM", "AZURE_DEVOPS_TEAM", "ADO_TEAM")
ENV_PROCESS = ("AGILE_WORKFLOW_AZURE_PROCESS", "ADO_PROCESS")

MCP_SERVER_KEYS = ("azure-devops", "Azure DevOps", "azure_devops")


@dataclass(frozen=True)
class AzureConfig:
    org: str | None = None
    project: str | None = None
    team: str | None = None
    process: str | None = None
    """agile | scrum | cmmi -- decides whether Original Estimate exists on this project."""

    def as_dict(self) -> dict[str, str]:
        pairs = (("org", self.org), ("project", self.project),
                 ("team", self.team), ("process", self.process))
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

    def with_azure(self, **kwargs: str | None) -> ProjectConfig:
        updates = {k: v for k, v in kwargs.items() if v}
        if not updates:
            return self
        return replace(self, azure=replace(self.azure, **updates))

    def with_artifacts_path(self, path: str | None) -> ProjectConfig:
        return replace(self, artifacts_path=path) if path else self

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
    """`.agile-backlog-toolkit/` -- where the plugin keeps its own state.

    Distinct from the artifacts path: this holds plugin internals (config, reports, the
    mistakes record), never the user's work products.
    """
    return Path(project_root) / PLUGIN_DIRNAME


def config_path(project_root: Path) -> Path:
    return Path(project_root) / CONFIG_RELPATH


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _str_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def org_from_mcp(data: dict[str, Any] | None) -> str | None:
    """Pull the organisation out of an MCP server definition.

    The org is the trailing positional argument of the Azure DevOps MCP command, whether
    launched through npx or directly via node.
    """
    if not data:
        return None
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return None
    for key in MCP_SERVER_KEYS:
        entry = servers.get(key)
        if not isinstance(entry, dict):
            continue
        args = entry.get("args")
        if not isinstance(args, list):
            continue
        for candidate in reversed(args):
            text = _str_or_none(candidate)
            if text and not text.startswith("-") and "/" not in text and not text.endswith(".js"):
                return text
    return None


def load_project_config(project_root: Path) -> ProjectConfig:
    """Resolve configuration for a project. Never raises; absent sources are skipped."""
    root = Path(project_root)
    sources: list[str] = []
    artifacts = org = project = team = process = linear_team = None
    provider_mode = "local"

    data = _read_json(config_path(root))
    if data:
        sources.append(str(CONFIG_RELPATH))
        artifacts = _str_or_none(data.get("artifacts_path"))
        provider_mode = _str_or_none(data.get("provider_mode")) or provider_mode
        azure = data.get("azure")
        if isinstance(azure, dict):
            org = _str_or_none(azure.get("org"))
            project = _str_or_none(azure.get("project"))
            team = _str_or_none(azure.get("team"))
            process = _str_or_none(azure.get("process"))
        linear = data.get("linear")
        if isinstance(linear, dict):
            linear_team = _str_or_none(linear.get("team"))

    manifest = _read_json(root / INSTALL_MANIFEST)
    if manifest:
        sources.append(INSTALL_MANIFEST)
        org = org or _str_or_none(manifest.get("azure_devops_org"))
        project = project or _str_or_none(manifest.get("azure_project"))
        team = team or _str_or_none(manifest.get("azure_team"))

    if not org:
        for relpath in MCP_FILES:
            candidate = org_from_mcp(_read_json(root / relpath))
            if candidate:
                org = candidate
                sources.append(str(relpath))
                break

    overrides = {
        "artifacts": _env(ENV_ARTIFACTS),
        "org": _env(ENV_ORG),
        "project": _env(ENV_PROJECT),
        "team": _env(ENV_TEAM),
        "process": _env(ENV_PROCESS),
    }
    if any(overrides.values()):
        sources.insert(0, "environment")

    return ProjectConfig(
        artifacts_path=overrides["artifacts"] or artifacts,
        azure=AzureConfig(
            org=overrides["org"] or org,
            project=overrides["project"] or project,
            team=overrides["team"] or team,
            process=overrides["process"] or process,
        ),
        linear=LinearConfig(team=linear_team),
        provider_mode=provider_mode,
        sources=tuple(sources),
    )


def save_project_config(project_root: Path, config: ProjectConfig) -> Path | None:
    """Persist to `.agile-backlog-toolkit/config.json`, preserving unknown keys already present."""
    path = config_path(project_root)
    existing = _read_json(path) or {}
    existing.update(config.as_dict())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return path


def update_config(
    project_root: Path,
    *,
    artifacts_path: str | None = None,
    **azure: str | None,
) -> ProjectConfig:
    """Merge values into the stored config and persist. Used by lazy fill."""
    config = load_project_config(project_root).with_azure(**azure).with_artifacts_path(artifacts_path)
    save_project_config(project_root, config)
    return config
