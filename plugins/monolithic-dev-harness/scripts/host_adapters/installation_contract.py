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


@dataclass(frozen=True)
class InstallationContext:
    home: Path
    projects: tuple[Path, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()

    def value(self, name: str, fallback: Path) -> Path:
        return Path(dict(self.environment).get(name, str(fallback))).expanduser()


@dataclass(frozen=True)
class Location:
    path: Path
    scope: str
    kind: str


@dataclass(frozen=True)
class Component:
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
    components: tuple[Component, ...] = ()
    errors: tuple[str, ...] = ()
    searched: tuple[Path, ...] = ()


@dataclass(frozen=True)
class Repair:
    action: Literal[
        "remove_entry", "remove_path", "archive_backup", "remove_provider_conflict"
    ]
    component: Component
    reason: str


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    components: tuple[Component, ...]
    repairs: tuple[Repair, ...] = ()


@dataclass(frozen=True)
class ProjectAsset:
    path: Path
    kind: str
    text: str = ""
    target: Path | None = None


@dataclass(frozen=True)
class InstallationAdapter:
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


def adapter_for(host: str) -> Result[InstallationAdapter]:
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
