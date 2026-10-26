"""Installation journals, project assets and configuration restoration."""

from __future__ import annotations

import json
from pathlib import Path

from core.result import Result, attempt, bind, require, sequence
from harness.installation_files import (
    MARKER,
    _apply,
    _atomic,
    _exclude_record,
    _exclude_restore,
    _read,
    _record,
    _remove,
    _require_ok,
    _restore,
    _safe,
    _safe_receipt_path,
    _safe_removal,
    _serialize,
    check_package_destination,
)
from harness.installation_scope import _context, _user_root
from host_adapters.installation_contract import ProjectAsset, adapter_for


def install_local(project: Path, plugin: Path, hosts: tuple[str, ...]) -> Result[Path]:
    from harness.installation_scope import scope_environment

    return bind(
        scope_environment("local", project, Path.home()),
        lambda _: bind(
            sequence(
                bind(
                    adapter_for(host),
                    lambda adapter: adapter.project_assets(project, plugin),
                )
                for host in hosts
            ),
            lambda plans: attempt(
                lambda: _install(
                    project.resolve(),
                    plugin,
                    hosts,
                    tuple(asset for plan in plans for asset in plan),
                ),
                "installation_failed",
                "project installation failed",
                OSError,
                ValueError,
                TypeError,
            ),
        ),
    )


def check_local(
    project: Path, source: Path, destination: Path, hosts: tuple[str, ...]
) -> Result[bool]:
    from dataclasses import replace

    return bind(
        sequence(
            bind(
                adapter_for(host),
                lambda adapter: adapter.project_assets(project, source),
            )
            for host in hosts
        ),
        lambda plans: attempt(
            lambda: _check_records(
                project.resolve(),
                tuple(
                    replace(
                        asset,
                        target=destination / asset.target.relative_to(source)
                        if asset.target
                        else None,
                    )
                    for plan in plans
                    for asset in plan
                ),
                destination.parents[1],
            ),
            "installation_conflict",
            "project upgrade preflight failed",
            OSError,
            ValueError,
            TypeError,
        ),
    )


def _check_records(
    project: Path, assets: tuple[ProjectAsset, ...], runtime: Path
) -> bool:
    check_package_destination(runtime)
    check_package_destination(runtime.with_name(runtime.name + ".new"))
    registered_projects()
    receipt = project / ".harness/installation.json"
    previous = _previous_receipt(receipt, "local")
    tuple(_restore(record) for record in previous.get("assets", ()))
    tuple(
        _record(
            asset, project, {item["path"]: item for item in previous.get("assets", ())}
        )
        for asset in assets
    )
    _exclude_record(project, tuple(asset.path for asset in assets))
    return True


def _install(
    project: Path,
    plugin: Path,
    hosts: tuple[str, ...],
    assets: tuple[ProjectAsset, ...],
) -> Path:
    receipt = project / ".harness/installation.json"
    previous = _previous_receipt(receipt, "local")
    records = tuple(
        _record(
            asset, project, {item["path"]: item for item in previous.get("assets", ())}
        )
        for asset in {str(item.path): item for item in assets}.values()
    )
    document = {
        "schema": 1,
        "product": MARKER,
        "scope": "local",
        "project": str(project),
        "plugin": str(plugin),
        "version": json.loads((plugin / ".claude-plugin/plugin.json").read_text())[
            "version"
        ],
        "hosts": list(dict.fromkeys((*previous.get("hosts", ()), *hosts))),
        "assets": list(
            {
                item["path"]: item for item in (*previous.get("assets", ()), *records)
            }.values()
        ),
        "git_exclude": _exclude_record(
            project, tuple(Path(item["path"]) for item in records)
        ),
    }
    _atomic(
        _safe(receipt, project),
        json.dumps({**document, "status": "installing"}, indent=2) + "\n",
    )
    record_projects((*registered_projects(), project))
    tuple(_apply(record) for record in records)
    match document["git_exclude"]:
        case {"path": path, "after": text}:
            _atomic(Path(path), text)
        case None:
            pass
    return _atomic(
        receipt, json.dumps({**document, "status": "installed"}, indent=2) + "\n"
    )


def remove_receipt(receipt: Path) -> Result[tuple[Path, ...]]:
    return attempt(
        lambda: _uninstall(receipt),
        "removal_failed",
        "receipt removal failed",
        OSError,
        ValueError,
        KeyError,
        TypeError,
    )


def _uninstall(receipt: Path) -> tuple[Path, ...]:
    restored = _receipt_plan(receipt)
    tuple(_remove(path, text) for path, text in restored)
    receipt.unlink()
    record_projects(
        tuple(
            project
            for project in registered_projects()
            if project / ".harness/installation.json" != receipt
        )
    )
    return tuple(path for path, _ in restored)


def _receipt_plan(receipt: Path) -> tuple[tuple[Path, str | None], ...]:
    document = json.loads(receipt.read_text())
    match document.get("product"), document.get("schema"), document.get("scope"):
        case "monolithic-dev-harness", 1, "user" if (
            receipt == _user_root() / "installation.json"
        ):
            permitted = frozenset(_user_config_paths(tuple(document.get("hosts", ()))))
            match all(
                Path(record["path"]) in permitted
                and _safe_removal(Path(record["path"]), _context(()))
                for record in document.get("assets", ())
            ):
                case True:
                    match document.get("status"):
                        case "installing":
                            return _pending_user_plan(document)
                        case _:
                            pass
                    return tuple(
                        _restore(record) for record in document.get("assets", ())
                    )
                case False:
                    raise ValueError(
                        "user receipt contains paths outside the selected host profiles"
                    )
        case "monolithic-dev-harness", 1, "local":
            project = Path(document["project"])
            match receipt == project / ".harness/installation.json":
                case False:
                    raise ValueError("receipt project mismatch")
                case True:
                    restored = tuple(
                        _restore(
                            {
                                **record,
                                "path": str(
                                    _safe_receipt_path(Path(record["path"]), project)
                                ),
                            }
                        )
                        for record in document["assets"]
                    )
                    return restored + _exclude_restore(
                        project, document.get("git_exclude")
                    )
        case _:
            raise ValueError("unsupported installation receipt")


def _pending_user_plan(document: dict) -> tuple[tuple[Path, str | None], ...]:
    from harness.installation_cleanup import rewrite_document
    from harness.installation_inventory import scan

    permitted = frozenset(_user_config_paths(tuple(document.get("hosts", ()))))
    pending = document.get("pending", {})
    match all(
        Path(path) in permitted
        and _safe_removal(Path(path), _context(()))
        and not Path(path).is_symlink()
        for path in pending
    ):
        case False:
            raise ValueError("pending installation references a changed host profile")
        case True:
            inventory = scan(_context(()))
            cleaned = tuple(
                (Path(path), _clean_snapshot(Path(path), inventory, rewrite_document))
                for path in pending
                if not path.endswith(".pre-harness")
            )
            return tuple(
                _restore(record)
                for record in document.get("assets", ())
                if record["path"] not in pending
            ) + tuple(
                (
                    path,
                    None
                    if pending[str(path)] is None and _empty_config(path, text)
                    else text,
                )
                for path, text in cleaned
            )


def _empty_config(path: Path, text: str | None) -> bool:
    import tomllib

    from harness.installation_inventory import json_document

    match text, path.suffix:
        case None, _:
            return True
        case str(), ".json" | ".jsonc":
            return json_document(text) == {}
        case str(), ".toml":
            return tomllib.loads(text) == {}
        case _:
            return False


def _user_config_paths(hosts: tuple[str, ...]) -> tuple[Path, ...]:
    return tuple(
        dict.fromkeys(
            location.path
            for host in hosts
            for location in _require_ok(adapter_for(host)).locations(_context(()))
            if location.scope == "user"
            and location.kind in ("settings", "hook", "mcp", "backup")
        )
    )


def begin_user(hosts: tuple[str, ...]) -> Result[Path]:
    plugin = Path(__file__).resolve().parents[2]
    return bind(
        sequence(
            bind(
                adapter_for(host),
                lambda adapter: bind(
                    adapter.preflight_user(_context(()), plugin),
                    lambda valid: require(
                        valid,
                        "installation_conflict",
                        "native adapter refused the destination",
                    ),
                ),
            )
            for host in hosts
        ),
        lambda _: attempt(
            lambda: _begin_user(hosts),
            "receipt_failed",
            "user installation preflight failed",
            OSError,
            ValueError,
            TypeError,
        ),
    )


def _begin_user(hosts: tuple[str, ...]) -> Path:
    from harness.installation_cleanup import rewrite_document
    from harness.installation_inventory import scan

    check_package_destination(_user_root() / "marketplace")
    check_package_destination(_user_root() / "marketplace.new")
    receipt = _user_root() / "installation.json"
    previous = _previous_receipt(receipt, "user")
    inventory = scan(_context(()))
    match inventory.errors:
        case ():
            tuple(_profile_path(path) for path in _user_config_paths(hosts))
            originals = {
                record["path"]: _restore(record)[1]
                for record in previous.get("assets", ())
            }
            pending = {
                str(path): originals.get(
                    str(path), _clean_snapshot(path, inventory, rewrite_document)
                )
                for path in _user_config_paths(hosts)
            }
            return _atomic(
                receipt,
                json.dumps(
                    {
                        **previous,
                        "schema": 1,
                        "product": MARKER,
                        "scope": "user",
                        "hosts": list(
                            dict.fromkeys((*previous.get("hosts", ()), *hosts))
                        ),
                        "status": "installing",
                        "pending": pending,
                    },
                    indent=2,
                )
                + "\n",
            )
        case _:
            raise ValueError(
                "uninspected host configuration; run harness doctor --installations before installation"
            )


def _profile_path(path: Path) -> Path:
    match (
        path.is_symlink()
        or any(parent.is_symlink() for parent in path.parents)
        or (path.exists() and not path.is_file())
    ):
        case True:
            raise ValueError(
                f"host configuration is a symlink or directory: {path}; use project scope or prepare a regular private configuration"
            )
        case False:
            return path


def _clean_snapshot(path: Path, inventory, rewrite) -> str | None:
    match _read(path):
        case None:
            return None
        case text:
            selectors = tuple(
                component.selector
                for component in inventory.components
                if component.path == path and component.selector and component.owned
            )
            return (
                _require_ok(rewrite(text, path.suffix, selectors))
                if selectors
                else text
            )


def record_user(plugin: Path, hosts: tuple[str, ...]) -> Result[Path]:
    return bind(
        sequence(
            bind(
                adapter_for(host),
                lambda adapter, host=host: bind(
                    adapter.verify_user(_context(())),
                    lambda verified: require(
                        verified,
                        "installation_unverified",
                        f"{host} did not confirm the requested installation",
                    ),
                ),
            )
            for host in hosts
        ),
        lambda _: attempt(
            lambda: _record_user(plugin, hosts),
            "receipt_failed",
            "could not record user installation",
            OSError,
            ValueError,
            TypeError,
        ),
    )


def _record_user(plugin: Path, hosts: tuple[str, ...]) -> Path:
    from harness.installation_inventory import scan

    receipt = _user_root() / "installation.json"
    previous = _previous_receipt(receipt, "user")
    assets = tuple(
        {"path": path, "kind": "file", "before": before, "after": _read(Path(path))}
        for path, before in previous.get("pending", {}).items()
        if _read(Path(path)) is not None and _read(Path(path)) != before
    )
    return _atomic(
        receipt,
        json.dumps(
            {
                "schema": 1,
                "product": MARKER,
                "scope": "user",
                "status": "installed",
                "version": json.loads(
                    (plugin / ".claude-plugin/plugin.json").read_text()
                )["version"],
                "plugin": str(plugin),
                "hosts": list(dict.fromkeys((*previous.get("hosts", ()), *hosts))),
                "assets": list(
                    {
                        item["path"]: item
                        for item in (*previous.get("assets", ()), *assets)
                    }.values()
                ),
                "inventory": _serialize(scan(_context(()))),
            },
            indent=2,
        )
        + "\n",
    )


def _previous_receipt(path: Path, scope: str) -> dict:
    match _read(path):
        case None:
            return {}
        case text:
            value = json.loads(text)
            match value:
                case {
                    "product": "monolithic-dev-harness",
                    "schema": 1,
                    "scope": str() as recorded,
                } if (
                    recorded == scope
                    and isinstance(value.get("assets", []), list)
                    and all(
                        _valid_record(record, path, scope)
                        for record in value.get("assets", [])
                    )
                    and isinstance(value.get("pending", {}), dict)
                ):
                    return value
                case _:
                    raise ValueError(
                        f"unrecognized or malformed installation receipt: {path}; preserve it and inspect provenance before retrying"
                    )


def _valid_record(record, receipt: Path, scope: str) -> bool:
    match record:
        case {"path": str() as path, "kind": "symlink", "target": str()}:
            return (
                Path(path).is_absolute()
                and ".." not in Path(path).parts
                and (
                    scope != "local" or Path(path).is_relative_to(receipt.parent.parent)
                )
            )
        case {"path": str() as path, "kind": "file" | "executable", "after": str()} if (
            record.get("before") is None or isinstance(record.get("before"), str)
        ):
            return (
                Path(path).is_absolute()
                and ".." not in Path(path).parts
                and (
                    scope != "local" or Path(path).is_relative_to(receipt.parent.parent)
                )
            )
        case _:
            return False


def registered_projects() -> tuple[Path, ...]:
    """Project registration references; this does not enable a user-wide adapter."""
    path = _user_root() / "projects.json"
    match _read(path):
        case None:
            return ()
        case text:
            value = json.loads(text)
            match value:
                case {
                    "product": "monolithic-dev-harness",
                    "schema": 1,
                    "projects": list() as projects,
                } if all(
                    isinstance(project, str)
                    and Path(project).is_absolute()
                    and ".." not in Path(project).parts
                    for project in projects
                ):
                    return tuple(Path(project) for project in projects)
                case _:
                    raise ValueError(f"unrecognized project registration index: {path}")


def record_projects(projects: tuple[Path, ...]) -> Path:
    path = _user_root() / "projects.json"
    match projects:
        case ():
            path.unlink(missing_ok=True)
            return path
        case _:
            return _atomic(
                path,
                json.dumps(
                    {
                        "product": MARKER,
                        "schema": 1,
                        "scope": "user",
                        "status": "installed",
                        "projects": [
                            str(project) for project in dict.fromkeys(projects)
                        ],
                    },
                    indent=2,
                )
                + "\n",
            )
