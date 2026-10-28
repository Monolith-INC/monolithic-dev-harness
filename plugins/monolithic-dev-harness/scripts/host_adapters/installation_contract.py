"""Versioned, vendor-neutral installation discovery and repair contract."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.result import Ok, Result, attempt, bind, err
from host_adapters.subagents import ADAPTERS

VERSION = 1
"""Contract version an adapter must declare to be accepted."""


@dataclass(frozen=True)
class InstallationContext:
    """Home directory, known projects and environment overrides for a scan."""

    home: Path
    projects: tuple[Path, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()

    def value(self, name: str, fallback: Path) -> Path:
        """Path from environment variable `name`, or `fallback` when it is unset."""
        return Path(dict(self.environment).get(name, str(fallback))).expanduser()


@dataclass(frozen=True)
class Location:
    """One path an adapter asks the inventory to inspect, with its scope and kind."""

    path: Path
    scope: str
    kind: str


@dataclass(frozen=True)
class Component:
    """One installed harness piece found in a host's configuration.

    `selector` addresses the entry inside its file; `project` is set for local scope.
    """

    kind: str
    host: str
    scope: str
    path: Path
    version: str | None = None
    detail: str = ""
    owned: bool = False
    digest: str = ""
    selector: tuple[str | int, ...] = ()
    project: Path | None = None


@dataclass(frozen=True)
class Inventory:
    """Components found, errors raised and paths searched by a scan."""

    components: tuple[Component, ...] = ()
    errors: tuple[str, ...] = ()
    searched: tuple[Path, ...] = ()


@dataclass(frozen=True)
class Repair:
    """One action that fixes a finding by removing or archiving a component."""

    action: Literal["remove_entry", "remove_path", "archive_backup"]
    component: Component
    reason: str


@dataclass(frozen=True)
class Finding:
    """A problem in the inventory, its components and the repairs that resolve it."""

    code: str
    message: str
    components: tuple[Component, ...]
    repairs: tuple[Repair, ...] = ()


@dataclass(frozen=True)
class ProjectAsset:
    """A file or link the harness places in a project for a host."""

    path: Path
    kind: str
    text: str = ""
    target: Path | None = None


@dataclass(frozen=True)
class InstallationAdapter:
    """A host's installation layout and native operations.

    `locations` lists the paths to inspect. `hook_metadata` names keys under a settings
    file's `hooks` table that hold host metadata rather than event groups.
    """

    host: str
    locations: Callable[[InstallationContext], tuple[Location, ...]]
    version: int = VERSION
    project_assets: Callable[[Path, Path], Result[tuple[ProjectAsset, ...]]] | None = (
        None
    )
    discover_projects: (
        Callable[[InstallationContext], Result[tuple[Path, ...]]] | None
    ) = None
    removal_commands: (
        Callable[[InstallationContext], Result[tuple[tuple[str, ...], ...]]] | None
    ) = None
    verify_user: Callable[[InstallationContext], Result[bool]] | None = None
    preflight_user: Callable[[InstallationContext, Path], Result[bool]] | None = None
    hook_metadata: frozenset[str] = frozenset()


def adapter_for(host: str) -> Result[InstallationAdapter]:
    """Load and validate the installation adapter registered for `host`."""
    match ADAPTERS.get(host):
        case None:
            return err("unknown_installation_host", "host is not registered")
        case module:
            return bind(
                attempt(
                    lambda: importlib.import_module(module).installation(),
                    "invalid_installation_adapter",
                    "adapter must implement the current installation contract",
                    AttributeError,
                    ImportError,
                ),
                _validate,
            )


def _validate(value: object) -> Result[InstallationAdapter]:
    match value:
        case InstallationAdapter(version=version) if (
            version == VERSION
            and callable(value.locations)
            and callable(value.project_assets)
            and callable(value.discover_projects)
            and callable(value.removal_commands)
            and callable(value.verify_user)
            and callable(value.preflight_user)
        ):
            return Ok(value)
        case _:
            return err(
                "invalid_installation_adapter",
                "adapter has an incompatible installation interface",
            )
