"""Coordinate install, discovery and scoped removal through the adapter contract."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from core.result import Err, Ok, Result, attempt, bind, sequence
from harness.installation_files import (
    _atomic,
    _fingerprint,
    _remove,
    _repair_writes,
    _require_ok,
    _safe_removal,
    remove_empty_directory,
)
from harness.installation_files import _serialize as _serialize
from harness.installation_files import apply_repairs as apply_repairs
from harness.installation_receipts import (
    _receipt_plan,
    begin_user,
    check_local,
    record_projects,
    record_user,
    registered_projects,
)
from harness.installation_receipts import install_local as install_local
from harness.installation_receipts import remove_receipt as remove_receipt
from harness.installation_scope import _context as _context
from harness.installation_scope import _user_root
from host_adapters.installation_contract import adapter_for


def inventory_report(projects: tuple[Path, ...]) -> dict:
    from harness.installation_inventory import findings, scan

    inventory = scan(_context(projects))
    return {
        "inventory": _serialize(inventory),
        "findings": _serialize(findings(inventory)),
        "coverage": "Current user profiles and explicit project roots; static presence does not establish runtime activation.",
    }


def discover_projects(projects: tuple[Path, ...]) -> Result[tuple[Path, ...]]:
    from host_adapters.subagents import ADAPTERS

    return bind(
        sequence(
            bind(
                adapter_for(host),
                lambda adapter: adapter.discover_projects(_context(projects)),
            )
            for host in ADAPTERS
        ),
        lambda groups: Ok(
            tuple(
                dict.fromkeys(
                    (
                        *projects,
                        *registered_projects(),
                        *(path for group in groups for path in group),
                    )
                )
            )
        ),
    )


def uninstall(
    scope: str, projects: tuple[Path, ...], purge: bool = False
) -> Result[tuple[Path, ...]]:
    match scope:
        case "all":
            return bind(
                discover_projects(projects),
                lambda roots: attempt(
                    lambda: _uninstall_all(scope, roots, purge),
                    "removal_failed",
                    "removal preflight or application failed",
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    subprocess.SubprocessError,
                ),
            )
        case _:
            return attempt(
                lambda: _uninstall_all(scope, projects, purge),
                "removal_failed",
                "removal preflight or application failed",
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            )


def _uninstall_all(
    scope: str, projects: tuple[Path, ...], purge: bool
) -> tuple[Path, ...]:
    from dataclasses import replace

    from harness.installation_cleanup import plan_cleanup
    from harness.installation_inventory import scan
    from host_adapters.subagents import ADAPTERS

    context = _context(projects)
    known_projects = registered_projects()
    remaining_projects = tuple(
        project
        for project in known_projects
        if scope == "user" or project not in projects
    )
    shared_paths = (
        _user_root() / "marketplace",
        _user_root() / "marketplace.new",
        Path(os.environ.get("HARNESS_BIN_DIR", str(Path.home() / ".local/bin")))
        / "harness",
    )
    receipts = tuple(
        project / ".harness/installation.json"
        for project in projects
        if scope in ("local", "all")
        and (project / ".harness/installation.json").is_file()
    ) + (
        (_user_root() / "installation.json",)
        if scope in ("user", "all") and (_user_root() / "installation.json").is_file()
        else ()
    )
    restore = tuple(entry for receipt in receipts for entry in _receipt_plan(receipt))
    inventory = scan(context)
    restored_paths = frozenset(path for path, _ in restore)
    filtered = replace(
        inventory,
        components=tuple(
            component
            for component in inventory.components
            if component.path not in restored_paths
        ),
    )
    repairs = tuple(
        repair
        for repair in _require_ok(plan_cleanup(filtered, scope, projects, purge))
        if not (
            (scope == "local" or remaining_projects)
            and any(
                repair.component.path == path or path in repair.component.path.parents
                for path in shared_paths
            )
        )
    )
    match all(
        repair.component in inventory.components
        and _fingerprint(repair.component)
        and _safe_removal(repair.component.path, context)
        for repair in repairs
    ):
        case False:
            raise ValueError("removal fingerprints or scope changed")
        case True:
            writes = _repair_writes(repairs)
            commands = (
                tuple(
                    command
                    for host in ADAPTERS
                    for command in _require_ok(
                        _require_ok(adapter_for(host)).removal_commands(context)
                    )
                )
                if scope in ("user", "all")
                else ()
            )
            # Every file rewrite, receipt and native command has been prepared before effects.
            tuple(_native_effect(command) for command in commands)
            tuple(_remove(path, text) for path, text in restore)
            tuple(_atomic(path, text) for path, text in writes)
            removals = tuple(
                dict.fromkeys(
                    repair.component.path
                    for repair in repairs
                    if repair.action == "remove_path"
                )
            )
            tuple(
                path.unlink(missing_ok=True)
                if path.is_symlink() or path.is_file()
                else shutil.rmtree(path)
                for path in sorted(
                    removals, key=lambda path: len(path.parts), reverse=True
                )
                if path.exists() or path.is_symlink()
            )
            tuple(receipt.unlink(missing_ok=True) for receipt in receipts)
            record_projects(remaining_projects)
            roots = (
                (_user_root(),)
                if scope in ("user", "all") and not remaining_projects
                else ()
            )
            tuple(
                remove_empty_directory(root)
                for root in roots
                if root / "installation.json" in receipts
                or any(
                    component.path in (root / "marketplace", root / "marketplace.new")
                    for component in inventory.components
                )
            )
            return tuple(
                dict.fromkeys(
                    (*restored_paths, *(path for path, _ in writes), *removals)
                )
            )


def _native_effect(command: tuple[str, ...]) -> tuple[str, ...]:
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=30, check=False
    )
    match result.returncode:
        case 0:
            return command
        case _:
            raise ValueError(
                f"native removal failed: {command[0]} {command[1:3]}; files and receipts retained for retry"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=("install", "check", "begin", "record", "uninstall", "inventory"),
    )
    parser.add_argument("--scope", choices=("local", "user", "all"), required=True)
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--host", default="")
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args(argv)
    projects = tuple(Path(path).expanduser().resolve() for path in args.project)
    match args.operation, args.scope, projects:
        case "inventory", _, _:
            print(json.dumps(inventory_report(projects), indent=2))
            return 0
        case "install", "local", (project,) if args.plugin and args.host:
            result = install_local(project, args.plugin, tuple(args.host.split(",")))
        case "check", "local", (project,) if (
            args.plugin and args.destination and args.host
        ):
            result = check_local(
                project, args.plugin, args.destination, tuple(args.host.split(","))
            )
        case "record", "user", _ if args.plugin:
            result = record_user(args.plugin, tuple(args.host.split(",")))
        case "begin", "user", _:
            result = begin_user(tuple(host for host in args.host.split(",") if host))
        case "uninstall", _, _:
            result = uninstall(args.scope, projects, args.purge)
        case _:
            parser.error("operation/scope/project/plugin combination is invalid")
    match result:
        case Ok(value):
            print(json.dumps({"ok": True, "result": _serialize(value)}))
            return 0
        case Err(failure):
            print(json.dumps({"ok": False, "error": failure.to_dict()}))
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
