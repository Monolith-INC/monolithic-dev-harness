"""Bounded read-only census of adapter-declared installation locations."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any

from core.result import Err, Ok, attempt
from host_adapters.installation_contract import (
    Component,
    Finding,
    InstallationContext,
    Inventory,
    Repair,
    adapter_for,
)
from host_adapters.subagents import ADAPTERS

MARKER = "monolithic-dev-harness"
MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json",
)
BLOCKS = (
    ("# BEGIN monolithic-dev-harness", "# END monolithic-dev-harness"),
    (
        "# >>> monolithic-dev-harness hooks (managed: install.sh --host kimi) >>>",
        "# <<< monolithic-dev-harness hooks <<<",
    ),
)


def json_document(text: str) -> Any:
    return json.loads(
        re.sub(
            r'("(?:\\.|[^"\\])*")|(?<=[}\]0-9"el])\s*,\s*(?=[}\]])',
            lambda found: found.group(1) or "",
            re.sub(
                r'("(?:\\.|[^"\\])*")|(/\*[\s\S]*?\*/|//[^\r\n]*)',
                lambda found: found.group(1) or "",
                text,
            ),
        )
    )


def digest(path: Path) -> str:
    return hashlib.sha256(
        str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
    ).hexdigest()


def scan(context: InstallationContext) -> Inventory:
    results = tuple(_host(host, context) for host in ADAPTERS)
    proofs = _backup_proofs(context)
    return Inventory(
        tuple(
            dict.fromkeys(
                _backup_component(item, proofs)
                for result in results
                for item in result.components
            )
        ),
        tuple(error for result in results for error in result.errors),
        tuple(dict.fromkeys(path for result in results for path in result.searched)),
    )


def _backup_proofs(context: InstallationContext) -> dict[Path, str]:
    from core.result import value_or

    paths = (
        context.value(
            "HARNESS_HOME", context.home / ".local/share/monolithic-dev-harness"
        )
        / "installation.json",
        *(project / ".harness/installation.json" for project in context.projects),
    )
    return {
        Path(record["path"]): hashlib.sha256(record["after"].encode()).hexdigest()
        for path in paths
        if path.is_file() and not path.is_symlink()
        for document in (
            value_or(
                attempt(
                    lambda path=path: json_document(path.read_text()),
                    "receipt_unreadable",
                    "cannot inspect backup ownership",
                    OSError,
                    ValueError,
                ),
                {},
            ),
        )
        if isinstance(document, dict) and document.get("product") == MARKER
        for record in (
            document.get("assets") if isinstance(document.get("assets"), list) else ()
        )
        if isinstance(record, dict)
        and record.get("before") is None
        and isinstance(record.get("after"), str)
        and str(record.get("path", "")).endswith(".pre-harness")
    }


def _backup_component(component: Component, proofs: dict[Path, str]) -> Component:
    from dataclasses import replace

    return (
        replace(
            component,
            kind="receipt-backup",
            owned=True,
            detail="backup ownership verified against installation receipt",
        )
        if component.kind == "backup" and proofs.get(component.path) == component.digest
        else component
    )


def _host(host: str, context: InstallationContext) -> Inventory:
    match adapter_for(host):
        case Ok(adapter):
            match attempt(
                lambda: adapter.locations(context),
                "locations",
                "cannot enumerate adapter paths",
                OSError,
            ):
                case Ok(locations):
                    results = tuple(
                        _location(
                            host,
                            location.path,
                            location.scope,
                            location.kind,
                            adapter.hook_metadata,
                        )
                        for location in locations
                    )
                    return Inventory(
                        tuple(
                            _project_scope(item, context)
                            for result in results
                            for item in result.components
                        ),
                        tuple(error for result in results for error in result.errors),
                        tuple(path for result in results for path in result.searched),
                    )
                case Err():
                    return Inventory(errors=(f"{host}:adapter:locations",))
        case Err():
            return Inventory(errors=(f"{host}:adapter:contract",))


def _project_scope(component: Component, context: InstallationContext) -> Component:
    from dataclasses import replace

    return (
        replace(
            component,
            project=max(
                (
                    project
                    for project in context.projects
                    if component.path.is_relative_to(project)
                ),
                key=lambda project: len(project.parts),
                default=None,
            ),
        )
        if component.scope == "local"
        else component
    )


def _location(
    host: str, path: Path, scope: str, kind: str, hook_metadata: frozenset[str]
) -> Inventory:
    try:
        path.lstat()
        return Inventory(
            _inspect(host, path, scope, kind, hook_metadata), searched=(path,)
        )
    except FileNotFoundError:
        return Inventory(searched=(path,))
    except (OSError, ValueError, TypeError, AttributeError):
        return Inventory(
            errors=(f"{host}:{path}:unreadable-or-invalid",), searched=(path,)
        )


def _component(
    host: str,
    path: Path,
    scope: str,
    kind: str,
    detail: str,
    selector=(),
    version=None,
    fingerprint=None,
    owned=True,
) -> Component:
    return Component(
        kind,
        host,
        scope,
        path,
        version,
        detail,
        owned,
        digest(path) if fingerprint is None else fingerprint,
        selector,
    )


def _manifest(path: Path) -> dict | None:
    match path.is_file():
        case False:
            return None
        case True:
            value = json_document(path.read_text())
            return (
                value
                if isinstance(value, dict)
                and value.get("name") == MARKER
                and isinstance(value.get("version"), str)
                else None
            )


def _package_manifest(root: Path) -> Path | None:
    return next(
        (
            path
            for base in (
                root,
                root / "marketplace/plugins" / MARKER,
                root / "plugins" / MARKER,
            )
            for name in MANIFESTS
            for path in (base / name,)
            if _manifest(path)
        ),
        None,
    )


def _verified_target(target: Path) -> bool:
    return any(
        _package_manifest(parent) is not None
        for parent in (target, *target.parents)
        if parent.name == MARKER
    )


def _inspect(
    host: str,
    path: Path,
    scope: str,
    kind: str,
    hook_metadata: frozenset[str] = frozenset(),
) -> tuple[Component, ...]:
    match path.is_symlink(), path.is_dir(), kind:
        case True, _, _:
            return (
                (_component(host, path, scope, kind, f"asset:{path.name}"),)
                if _verified_target(path.resolve())
                else ()
            )
        case _, True, "installation" | "cache":
            match _package_manifest(path):
                case Path() as manifest:
                    return (
                        _component(
                            host,
                            path,
                            scope,
                            kind,
                            "manifest:" + manifest.relative_to(path).as_posix(),
                            version=_manifest(manifest)["version"],
                            fingerprint=digest(manifest),
                        ),
                    )
                case None:
                    return ()
        case _, True, "skill" | "agent":
            return tuple(
                component
                for entry in sorted(path.iterdir())
                for component in _inspect_asset(host, entry, scope, kind)
            )
        case _, True, "state":
            return (
                _component(
                    host, path, scope, kind, "dedicated harness state", fingerprint=""
                ),
            )
        case _, True, _:
            return ()
        case _, _, "backup":
            return (
                _component(
                    host,
                    path,
                    scope,
                    kind,
                    "legacy settings backup; ownership requires a receipt",
                    owned=False,
                ),
            )
        case _, _, "dedicated-settings":
            return (_component(host, path, scope, kind, "dedicated harness settings"),)
        case _, _, "installation" | "cache" if _manifest(path):
            return (
                _component(
                    host,
                    path,
                    scope,
                    kind,
                    "product manifest",
                    version=_manifest(path)["version"],
                ),
            )
        case _:
            return _settings(host, path, scope, kind, hook_metadata)


def _inspect_asset(
    host: str, path: Path, scope: str, kind: str
) -> tuple[Component, ...]:
    match path.is_symlink(), path.is_file():
        case True, _:
            return _inspect(host, path, scope, kind)
        case False, True if (
            path.suffix == ".toml"
            and "# managed by monolithic-dev-harness"
            in path.read_text().splitlines()[:3]
        ):
            return (_component(host, path, scope, kind, f"asset:{path.name}"),)
        case _:
            return ()


def _owned(value: Any) -> bool:
    match value:
        case {"command": str() as command}:
            words = (*shlex.split(command), *value.get("args", ()))
            executable = (
                words[1]
                if len(words) > 1 and words[0] in ("sh", "bash")
                else (words[0] if words else "")
            )
            return (
                isinstance(executable, str)
                and MARKER in Path(executable).parts
                and executable.endswith(
                    ("/bin/harness-python", "/scripts/harness/hook.py")
                )
            )
        case _:
            return False


def _settings(
    host: str, path: Path, scope: str, kind: str, hook_metadata: frozenset[str]
) -> tuple[Component, ...]:
    text = path.read_text()
    match kind:
        case "receipt":
            from harness.installation_receipts import _previous_receipt

            value = _previous_receipt(path, scope)
            return (
                (
                    _component(
                        host,
                        path,
                        scope,
                        kind,
                        "receipt:" + str(value.get("status", "unknown")),
                        version=value.get("version"),
                    ),
                )
                if value.get("product") == MARKER
                else ()
            )
        case _:
            pass
    match path.suffix:
        case ".json" | ".jsonc":
            value = json_document(text)
        case ".toml":
            value = tomllib.loads(text)
        case _:
            return ()
    match value:
        case dict():
            servers = tuple(
                _component(host, path, scope, "mcp", f"server:{name}", (key, name))
                for key in ("mcpServers", "mcp_servers", "context_servers")
                for name, record in value.get(key, {}).items()
                if _owned(record)
            )
            hooks = _hooks(host, path, scope, value.get("hooks", {}), hook_metadata)
            blocks = tuple(
                _component(
                    host,
                    path,
                    scope,
                    "hook",
                    "managed hooks block",
                    ("__managed_block__",),
                )
                for begin, end in BLOCKS
                if begin in text and end in text
            )
            registrations = _registrations(host, path, scope, value, kind)
            conflicts = tuple(
                _component(
                    host,
                    path,
                    scope,
                    "provider-conflict",
                    f"private provider registered directly: {name}",
                    (key, name),
                    owned=False,
                )
                for key in ("mcpServers", "mcp_servers", "context_servers")
                if "workflow-integrations" in value.get(key, {})
                for name, record in value.get(key, {}).items()
                if native_provider(record)
            )
            return servers + (blocks or hooks) + registrations + conflicts
        case _:
            raise ValueError("host settings must be an object")


def native_provider(record: Any) -> bool:
    match record:
        case {"command": str() as command, **rest}:
            return any(
                str(word).startswith("@azure-devops/mcp")
                or str(word).endswith("mcp-server-azuredevops")
                for word in (command, *rest.get("args", ()))
            )
        case _:
            return False


def _hooks(
    host: str, path: Path, scope: str, hooks: Any, hook_metadata: frozenset[str]
) -> tuple[Component, ...]:
    match hooks:
        case dict():
            return tuple(
                component
                for event, groups in hooks.items()
                if event not in hook_metadata
                for index, group in enumerate(groups)
                for component in _hook_group(
                    host, path, scope, event, group, ("hooks", event, index)
                )
            )
        case list():
            return ()  # Kimi arrays are removed only through their managed block.
        case _:
            raise ValueError("hooks must be an object or an array")


def _hook_group(
    host: str, path: Path, scope: str, event: str, group: dict, selector: tuple
) -> tuple[Component, ...]:
    match group.get("hooks"):
        case list() as handlers if handlers and all(
            _owned(handler) for handler in handlers
        ):
            return (
                _component(
                    host,
                    path,
                    scope,
                    "hook",
                    f"event:{event}:{group.get('matcher', '')}",
                    selector,
                ),
            )
        case list() as handlers:
            return tuple(
                _component(
                    host,
                    path,
                    scope,
                    "hook",
                    f"event:{event}:{group.get('matcher', '')}",
                    selector + ("hooks", index),
                )
                for index, handler in enumerate(handlers)
                if _owned(handler)
            )
        case _:
            return (
                (
                    _component(
                        host,
                        path,
                        scope,
                        "hook",
                        f"event:{event}:{group.get('matcher', '')}",
                        selector,
                    ),
                )
                if _owned(group)
                else ()
            )


def _registrations(
    host: str, path: Path, scope: str, value: dict, kind: str
) -> tuple[Component, ...]:
    nested = tuple(
        _component(
            host,
            path,
            scope,
            "registration",
            f"plugin-installed:{name}"
            if path.name.startswith("installed")
            else f"plugin-enabled:{name}",
            ("plugins", name),
        )
        for name in value.get("plugins", {})
        if name in (MARKER, f"{MARKER}@{MARKER}")
    )
    root = (
        (
            _component(
                host, path, scope, "registration", "marketplace:" + MARKER, (MARKER,)
            ),
        )
        if kind == "registration" and MARKER in value
        else ()
    )
    enabled = tuple(
        _component(
            host,
            path,
            scope,
            "registration",
            f"plugin-enabled:{name}",
            ("enabledPlugins", name),
        )
        for name in value.get("enabledPlugins", {})
        if name == f"{MARKER}@{MARKER}"
    )
    return nested + root + enabled


def findings(
    inventory: Inventory, expected_version: str | None = None
) -> tuple[Finding, ...]:
    versions = frozenset(
        item.version
        for item in inventory.components
        if item.version and item.kind in ("installation", "cache")
    )
    stale = tuple(
        item
        for item in inventory.components
        if item.version
        and item.kind in ("installation", "cache")
        and (len(versions) > 1 or expected_version and item.version != expected_version)
    )
    duplicates = tuple(
        item
        for item in inventory.components
        if item.kind in ("hook", "mcp", "registration", "skill", "agent")
        and any(
            (other.host, other.kind, other.detail)
            == (item.host, item.kind, item.detail)
            and (
                other.project is None
                or item.project is None
                or other.project == item.project
            )
            and (other.path, other.selector) != (item.path, item.selector)
            for other in inventory.components
        )
    )
    return (
        tuple(
            Finding(
                "private-provider-registration",
                "This host also registers the provider privately owned by workflow-integrations. Select the exact local entry for removal; unrelated/global registrations are preserved.",
                (item,),
                (
                    Repair(
                        "remove_provider_conflict",
                        item,
                        "remove the explicitly selected conflicting local provider entry",
                    ),
                )
                if item.scope == "local"
                else (),
            )
            for item in inventory.components
            if item.kind == "provider-conflict"
        )
        + _scope_overlap(inventory)
        + tuple(
            item
            for item in (
                Finding(
                    "mixed-version" if len(versions) > 1 else "outdated-version",
                    "Installed versions differ"
                    if len(versions) > 1
                    else "Installed version differs from expectation",
                    stale,
                )
                if stale
                else None,
                Finding(
                    "duplicate-components",
                    "Potential overlapping harness components; select the installation to retain before removal",
                    duplicates,
                    tuple(
                        Repair(
                            "remove_entry" if item.selector else "remove_path",
                            item,
                            "remove selected duplicate component",
                        )
                        for item in duplicates
                    ),
                )
                if duplicates
                else None,
                Finding(
                    "legacy-backups",
                    "Legacy backups may contain unrelated settings; inspect and archive explicitly",
                    tuple(
                        item for item in inventory.components if item.kind == "backup"
                    ),
                    tuple(
                        Repair(
                            "archive_backup",
                            item,
                            "preserve the ambiguous backup outside active host configuration",
                        )
                        for item in inventory.components
                        if item.kind == "backup"
                    ),
                )
                if any(item.kind == "backup" for item in inventory.components)
                else None,
                Finding(
                    "incomplete-installation",
                    "Installation stopped before completion; inspect the journal and rerun installation or scoped removal",
                    tuple(
                        item
                        for item in inventory.components
                        if item.kind == "receipt" and item.detail != "receipt:installed"
                    ),
                )
                if any(
                    item.kind == "receipt" and item.detail != "receipt:installed"
                    for item in inventory.components
                )
                else None,
            )
            if item is not None
        )
    )


def _scope_overlap(inventory: Inventory) -> tuple[Finding, ...]:
    users = tuple(
        item
        for item in inventory.components
        if item.scope == "user" and item.kind in ("registration", "hook", "mcp")
    )
    locals_ = tuple(
        item
        for item in inventory.components
        if item.scope == "local"
        and item.kind in ("hook", "mcp", "skill", "agent", "registration")
    )
    conflicting = tuple(
        dict.fromkeys(
            item
            for user in users
            for local in locals_
            if user.host == local.host
            for item in (user, local)
        )
    )
    return (
        (
            Finding(
                "overlapping-scopes",
                "User and project registrations coexist. Shared package storage alone is not a registration. Keep the project installation with install.sh --uninstall --scope user, or select local entries below to retain the user installation.",
                conflicting,
                tuple(
                    Repair(
                        "remove_entry" if item.selector else "remove_path",
                        item,
                        "remove the selected project registration to retain the user installation",
                    )
                    for item in conflicting
                    if item.scope == "local" and item.owned
                ),
            ),
        )
        if conflicting
        else ()
    )
