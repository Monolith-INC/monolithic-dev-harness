"""Native configuration locations for the common installation inventory contract."""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.result import attempt

from .installation_contract import InstallationAdapter, InstallationContext, Location

PROFILES = {
    "claude": ("CLAUDE_CONFIG_DIR", ".claude"),
    "codex": ("CODEX_HOME", ".codex"),
    "cursor": ("CURSOR_CONFIG_DIR", ".cursor"),
    "kimi": ("KIMI_CONFIG_DIR", ".kimi-code"),
    "zed": ("ZED_CONFIG_DIR", ".config/zed"),
}
FILES = {
    "claude": (
        ("settings.json", "settings"),
        ("settings.local.json", "settings"),
        ("plugins/installed_plugins.json", "registration"),
        ("plugins/known_marketplaces.json", "registration"),
    ),
    "codex": (
        ("config.toml", "settings"),
        ("hooks.json", "hook"),
        ("plugins/installed_plugins.json", "registration"),
        ("plugins/installed.json", "registration"),
    ),
    "cursor": (("hooks.json", "hook"), ("mcp.json", "mcp")),
    "kimi": (
        ("config.toml", "settings"),
        ("config.toml.pre-harness", "backup"),
        ("mcp.json", "mcp"),
    ),
    "zed": (("settings.json", "settings"), ("settings.json.pre-harness", "backup")),
}


def adapter(host: str) -> InstallationAdapter:
    from .installation_project import assets

    return InstallationAdapter(
        host,
        lambda context: locations(host, context),
        project_assets=lambda project, plugin: assets(host, project, plugin),
        discover_projects=lambda context: _discover(host, context),
        removal_commands=lambda context: _native_removal(host, context),
        verify_user=lambda context: _verify_user(host, context),
        preflight_user=lambda context, plugin: _preflight_user(host, context, plugin),
    )


def _discover(host: str, context: InstallationContext):
    return attempt(
        lambda: _project_metadata(host, context),
        "project_discovery_failed",
        "host project metadata could not be inspected",
        OSError,
        ValueError,
        TypeError,
    )


def _project_metadata(host: str, context: InstallationContext) -> tuple[Path, ...]:
    import json
    import tomllib

    profile = _profile_root(host, context)
    path = (
        context.home / ".claude.json" if host == "claude" else profile / "config.toml"
    )
    match host, path.is_file():
        case "claude", True:
            value = json.loads(path.read_text())
        case "codex", True:
            value = tomllib.loads(path.read_text())
        case _:
            return ()
    return tuple(
        Path(name).resolve()
        for name in value.get("projects", {})
        if Path(name).is_absolute()
        and Path(name).is_dir()
        and Path(name).resolve() not in (context.home.resolve(), Path("/"))
    )


def _native_removal(host: str, context: InstallationContext):
    return attempt(
        lambda: _native_commands(host, context),
        "native_registration_unreadable",
        "could not inspect native plugin registration",
        OSError,
        ValueError,
        subprocess.SubprocessError,
    )


def _rows(value, key: str, fallback: str = "") -> tuple[dict, ...]:
    rows = value.get(key, value.get(fallback, ())) if isinstance(value, dict) else value
    match rows:
        case list() | tuple() if all(isinstance(row, dict) for row in rows):
            return tuple(rows)
        case _:
            raise ValueError("native plugin listing has an unsupported shape")


def _listing(binary: str, arguments: tuple[str, ...]):
    import json

    result = subprocess.run(
        (binary, *arguments, "--json"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    match result.returncode:
        case 0:
            return json.loads(result.stdout)
        case _:
            raise ValueError(
                f"{binary} {' '.join(arguments)} failed; inspect native registration before removal"
            )


def _installed_harness(item: dict) -> bool:
    return item.get(
        "pluginId", item.get("id")
    ) == "monolithic-dev-harness@monolithic-dev-harness" or (
        item.get("name"),
        item.get("marketplaceName"),
    ) == ("monolithic-dev-harness", "monolithic-dev-harness")


def _owned_marketplace(item: dict, host: str, context: InstallationContext) -> bool:
    import json

    expected = (
        context.value(
            "HARNESS_HOME", context.home / ".local/share/monolithic-dev-harness"
        )
        / "marketplace"
    )
    expected = expected / "codex-marketplace" if host == "codex" else expected
    root = item.get("root", item.get("installLocation"))
    match root:
        case str():
            receipt = (
                context.value(
                    "HARNESS_HOME", context.home / ".local/share/monolithic-dev-harness"
                )
                / "installation.json"
            )
            recorded = (
                json.loads(receipt.read_text())
                if receipt.is_file() and not receipt.is_symlink()
                else {}
            )
            previous = (
                Path(recorded["plugin"]).parents[1]
                if recorded.get("product") == "monolithic-dev-harness"
                and recorded.get("scope") == "user"
                and isinstance(recorded.get("plugin"), str)
                and len(Path(recorded["plugin"]).parents) > 1
                else None
            )
            previous = (
                previous / "codex-marketplace"
                if previous and host == "codex"
                else previous
            )
            return Path(root).resolve() in (
                expected.resolve(),
                previous.resolve() if previous else None,
            )
        case _:
            raise ValueError(
                f"{host} marketplace ownership cannot be established; inspect the native marketplace listing"
            )


def _native_commands(
    host: str, context: InstallationContext
) -> tuple[tuple[str, ...], ...]:
    import shutil

    match (
        host,
        shutil.which(host),
        _scope(_profile_root(host, context), context),
    ):
        case "claude" | "codex", str() as binary, "user" if _profile_root(
            host, context
        ).is_dir() or (
            host == "claude"
            and context.value(
                "CLAUDE_CODE_PLUGIN_CACHE_DIR", _profile_root(host, context) / "plugins"
            ).is_dir()
        ):
            installed = _rows(
                _listing(binary, ("plugin", "list")), "installed", "plugins"
            )
            marketplaces = tuple(
                item
                for item in _rows(
                    _listing(binary, ("plugin", "marketplace", "list")), "marketplaces"
                )
                if item.get("name") == "monolithic-dev-harness"
            )
            match all(_owned_marketplace(item, host, context) for item in marketplaces):
                case False:
                    raise ValueError(
                        f"{host} has a same-named marketplace from an unrelated source; preserve it and resolve the name collision"
                    )
                case True:
                    return (
                        (
                            (
                                binary,
                                "plugin",
                                "uninstall" if host == "claude" else "remove",
                                "monolithic-dev-harness@monolithic-dev-harness",
                            ),
                        )
                        if any(_installed_harness(item) for item in installed)
                        else ()
                    ) + (
                        (
                            (
                                binary,
                                "plugin",
                                "marketplace",
                                "remove",
                                "monolithic-dev-harness",
                            ),
                        )
                        if marketplaces
                        else ()
                    )
        case _:
            return ()


def _verify_user(host: str, context: InstallationContext):
    return attempt(
        lambda: _verified_user(host, context),
        "installation_unverified",
        "native registration or configured assets could not be verified",
        OSError,
        ValueError,
        subprocess.SubprocessError,
    )


def _verified_user(host: str, context: InstallationContext) -> bool:
    from harness.installation_inventory import scan

    match host:
        case "claude" | "codex":
            return any(
                command[1:3] in (("plugin", "uninstall"), ("plugin", "remove"))
                for command in _native_commands(host, context)
            )
        case _:
            return any(
                component.host == host and component.owned
                for component in scan(context).components
            )


def locations(host: str, context: InstallationContext) -> tuple[Location, ...]:
    return (
        receipt_locations(context, host)
        + _profile_locations(
            host,
            _profile_root(host, context),
            _scope(
                _profile_root(host, context),
                context,
            ),
        )
        + tuple(
            location
            for project in context.projects
            for location in _profile_locations(
                host,
                project / (".zed" if host == "zed" else PROFILES[host][1]),
                "local",
            )
        )
        + _extra_locations(host, context)
    )


def _scope(path: Path, context: InstallationContext) -> str:
    return (
        "local"
        if any(path.is_relative_to(project) for project in context.projects)
        else "user"
    )


def _profile_locations(host: str, profile: Path, scope: str) -> tuple[Location, ...]:
    return (
        tuple(Location(profile / name, scope, kind) for name, kind in FILES[host])
        + tuple(
            Location(profile / directory, scope, kind)
            for directory, kind in (("skills", "skill"), ("agents", "agent"))
        )
        + tuple(
            Location(path, scope, "installation") for path in _caches(host, profile)
        )
    )


def _caches(host: str, profile: Path) -> tuple[Path, ...]:
    match host:
        case "claude":
            return tuple(
                path
                for pattern in (
                    "*/monolithic-dev-harness/*",
                    "monolithic-dev-harness/*",
                )
                for path in (profile / "plugins/cache").glob(pattern)
            )
        case "codex":
            return tuple(
                path
                for pattern in (
                    "*/monolithic-dev-harness",
                    "*/monolithic-dev-harness/*",
                )
                for path in (profile / "plugins/cache").glob(pattern)
            )
        case "cursor":
            return (profile / "plugins/local/monolithic-dev-harness",)
        case _:
            return ()


def _extra_locations(host: str, context: InstallationContext) -> tuple[Location, ...]:
    match host:
        case "claude":
            return (
                runtime_locations(context)
                + (
                    Location(
                        context.value(
                            "HARNESS_HOME",
                            context.home / ".local/share/monolithic-dev-harness",
                        )
                        / "installation.json",
                        "user",
                        "receipt",
                    ),
                    Location(context.home / ".claude.json", "user", "registration"),
                    Location(
                        context.value("HARNESS_BIN_DIR", context.home / ".local/bin")
                        / "harness",
                        _scope(
                            context.value(
                                "HARNESS_BIN_DIR", context.home / ".local/bin"
                            ),
                            context,
                        ),
                        "launcher",
                    ),
                    Location(
                        context.value(
                            "HARNESS_USER_STATE_DIR",
                            context.value("XDG_CONFIG_HOME", context.home / ".config")
                            / "monolithic-dev-harness",
                        )
                        / "preferences.json",
                        _scope(
                            context.value(
                                "HARNESS_USER_STATE_DIR",
                                context.home / ".config/monolithic-dev-harness",
                            ),
                            context,
                        ),
                        "dedicated-settings",
                    ),
                )
                + tuple(
                    location
                    for project in context.projects
                    for location in (
                        Location(
                            project / ".harness/installation.json", "local", "receipt"
                        ),
                        Location(
                            project / ".harness/settings.json",
                            "local",
                            "dedicated-settings",
                        ),
                        Location(project / ".harness/state", "local", "state"),
                        Location(project / ".mcp.json", "local", "mcp"),
                    )
                )
            )
        case "kimi":
            return (
                tuple(
                    Location(profile / name, scope, kind)
                    for profile, scope in (
                        (
                            context.home / ".kimi",
                            "user",
                        ),
                        *((project / ".kimi", "local") for project in context.projects),
                    )
                    for name, kind in FILES["kimi"]
                )
                + tuple(
                    Location(
                        context.value("AGENTS_SHARED_DIR", context.home / ".agents")
                        / name,
                        "user",
                        kind,
                    )
                    for name, kind in (("skills", "skill"), ("agents", "agent"))
                )
                + tuple(
                    Location(project / ".agents" / name, "local", kind)
                    for project in context.projects
                    for name, kind in (("skills", "skill"), ("agents", "agent"))
                )
            )
        case "cursor":
            return (
                Location(
                    context.value(
                        "CURSOR_PLUGIN_DIR",
                        context.home / ".cursor/plugins/local/monolithic-dev-harness",
                    ),
                    "user",
                    "installation",
                ),
            )
        case _:
            return ()


def receipt_locations(context: InstallationContext, host: str) -> tuple[Location, ...]:
    import json

    path = (
        context.value(
            "HARNESS_HOME", context.home / ".local/share/monolithic-dev-harness"
        )
        / "installation.json"
    )
    match path.is_file():
        case False:
            return ()
        case True:
            value = json.loads(path.read_text())
            return tuple(
                Location(
                    Path(item["path"]) / "marketplace"
                    if item.get("detail", "").startswith("manifest:marketplace/")
                    else Path(item["path"]),
                    "user",
                    item["kind"],
                )
                for item in value.get("inventory", {}).get("components", ())
                if value.get("product") == "monolithic-dev-harness"
                and item.get("host") == host
                and item.get("scope") == "user"
                and item.get("kind")
                in (
                    "installation",
                    "cache",
                    "skill",
                    "agent",
                    "launcher",
                    "settings",
                    "registration",
                    "hook",
                    "mcp",
                )
                and Path(item["path"]).is_absolute()
            )


def _profile_root(host: str, context: InstallationContext) -> Path:
    return context.value(
        PROFILES[host][0],
        context.value("KIMI_CODE_HOME", context.home / ".kimi-code")
        if host == "kimi"
        else context.home / PROFILES[host][1],
    )


def _preflight_user(host: str, context: InstallationContext, plugin: Path):
    return attempt(
        lambda: _user_conflicts(host, context, plugin),
        "installation_conflict",
        "native installation preflight failed",
        OSError,
        ValueError,
        TypeError,
    )


def _user_conflicts(host: str, context: InstallationContext, plugin: Path) -> bool:
    from harness.installation_files import check_package_destination

    from .installation_project import _mcp_asset

    match host:
        case "cursor":
            return check_package_destination(
                context.value(
                    "CURSOR_PLUGIN_DIR",
                    context.home / ".cursor/plugins/local/monolithic-dev-harness",
                )
            )
        case "codex":
            agents = tuple(
                _profile_root(host, context) / "agents" / name
                for name in ("mdh_thermo_review.toml", "mdh_thermo_quality.toml")
            )
            match all(
                not path.exists()
                or path.is_file()
                and not path.is_symlink()
                and "# managed by monolithic-dev-harness"
                in path.read_text().splitlines()[:3]
                for path in agents
            ):
                case True:
                    return True
                case False:
                    raise ValueError(
                        "an unrelated file occupies a native review-agent name"
                    )
        case "zed":
            _mcp_asset(
                _profile_root(host, context) / "settings.json",
                plugin / "zed.mcp.json",
                plugin,
                "context_servers",
            )
            return True
        case "claude":
            import shutil

            match shutil.which("claude"):
                case str() as binary:
                    return all(
                        _owned_marketplace(item, host, context)
                        for item in _rows(
                            _listing(binary, ("plugin", "marketplace", "list")),
                            "marketplaces",
                        )
                        if item.get("name") == "monolithic-dev-harness"
                    )
                case _:
                    return False
        case _:
            return True


def runtime_locations(context: InstallationContext) -> tuple[Location, ...]:
    root = context.value(
        "HARNESS_HOME", context.home / ".local/share/monolithic-dev-harness"
    )
    roots = ((root, "user"),)
    return tuple(
        Location(path / name, scope, "installation")
        for path, scope in roots
        for name in ("marketplace", "marketplace.new")
    )
