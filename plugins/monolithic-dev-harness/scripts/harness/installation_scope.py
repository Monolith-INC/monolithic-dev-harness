"""Pure scope resolution shared by install, repair, removal and diagnostics."""

from __future__ import annotations

import os
from pathlib import Path

from core.result import Ok, Result, err


def scope_environment(
    scope: str, project: Path | None, home: Path
) -> Result[tuple[tuple[str, str], ...]]:
    match scope, project:
        case "user", _:
            return Ok(
                _paths(
                    home / ".local/share/monolithic-dev-harness",
                    home / ".local/bin",
                    home,
                    False,
                )
            )
        case "local", Path() if project.is_dir() and project.resolve() not in (
            home.resolve(),
            Path("/"),
        ):
            return Ok(
                _paths(
                    home / ".local/share/monolithic-dev-harness",
                    home / ".local/bin",
                    home,
                    False,
                )
            )
        case "local", _:
            return err(
                "invalid_installation_project",
                "local scope requires an existing project directory distinct from home and filesystem root",
            )
        case _:
            return err(
                "invalid_installation_scope",
                "installation scope must be user or local; all is removal-only and shared project scope is reserved",
            )


def _paths(
    root: Path, binary: Path, base: Path, local: bool
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (name, str(path))
        for name, path in (
            ("HARNESS_HOME", root),
            ("HARNESS_BIN_DIR", binary),
            (
                "HARNESS_USER_STATE_DIR",
                base / ".harness/state/preferences"
                if local
                else base / ".config/monolithic-dev-harness",
            ),
        )
    )


def _context(projects: tuple[Path, ...]):
    from host_adapters.installation_contract import InstallationContext

    return InstallationContext(Path.home(), projects, tuple(os.environ.items()))


def _user_root() -> Path:
    return Path(
        os.environ.get(
            "HARNESS_HOME", str(Path.home() / ".local/share" / "monolithic-dev-harness")
        )
    )
