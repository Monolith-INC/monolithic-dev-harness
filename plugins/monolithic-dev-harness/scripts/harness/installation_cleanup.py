"""Pure planning and ownership-checked document rewriting for installation cleanup."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from core.result import Ok, Result, err
from host_adapters.installation_contract import Component, Finding, Inventory, Repair

_PROTECTED = frozenset(
    {"project-source", "ticket", "documentation", "auth", "shared-credentials"}
)
_STANDALONE = frozenset({"installation", "cache", "skill", "agent", "launcher"})
_ENTRY_KINDS = frozenset({"registration", "hook", "mcp", "settings"})
_PURGE_PATH_KINDS = frozenset({"state", "dedicated-settings"})


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _eligible(
    component: Component,
    scope: str,
    roots: tuple[Path, ...],
    hosts: tuple[str, ...],
    purge: bool,
) -> bool:
    return all(
        (
            not hosts or component.host in hosts,
            scope != "user" or component.scope == "user",
            scope != "local"
            or (component.scope == "local" and _inside(component.path, roots)),
            scope != "all"
            or component.scope != "local"
            or _inside(component.path, roots),
            component.kind not in _PROTECTED,
            component.owned,
            component.kind in _STANDALONE
            or (component.kind in _ENTRY_KINDS and bool(component.selector))
            or (purge and component.kind in _PURGE_PATH_KINDS),
        )
    )


def _repair(component: Component, purge: bool) -> Repair | None:
    match component:
        case Component(kind=kind) if kind in _ENTRY_KINDS and component.selector:
            return Repair(
                "remove_entry", component, "deactivate owned registration entry"
            )
        case Component(kind=kind) if kind in _STANDALONE:
            return Repair(
                "remove_path",
                component,
                "remove standalone owned installation resource",
            )
        case Component(kind=kind) if purge and kind in _PURGE_PATH_KINDS:
            return Repair("remove_path", component, "purge owned installation state")
        case _:
            return None


def plan_cleanup(
    inventory: Inventory,
    scope: str,
    projects: tuple[Path, ...] = (),
    purge: bool = False,
    hosts: tuple[str, ...] = (),
) -> Result[tuple[Repair, ...]]:
    match scope, inventory.errors:
        case invalid, _ if invalid not in {"user", "local", "all"}:
            return err("invalid_scope", "scope must be user, local, or all")
        case "local", _ if not projects:
            return err(
                "project_roots_required",
                "local cleanup requires explicit project roots",
            )
        case _, errors if tuple(
            error
            for error in errors
            if _relevant_inventory_error(error, scope, projects, hosts)
        ):
            return err(
                "inventory_unreadable",
                "cannot guarantee clean cleanup: inventory contains unreadable declared paths",
            )
        case _:
            return Ok(
                tuple(
                    repair
                    for component in inventory.components
                    if _eligible(component, scope, projects, hosts, purge)
                    for repair in (_repair(component, purge),)
                    if repair is not None
                )
            )


def plan_repairs(
    findings: tuple[Finding, ...], keep_scope: str, keep_version: str | None
) -> Result[tuple[Repair, ...]]:
    match keep_scope:
        case "user" | "local" | "all":
            return Ok(
                tuple(
                    repair
                    for finding in findings
                    for repair in finding.repairs
                    if repair.component.owned
                    and repair.component.scope != keep_scope
                    and repair.component.version != keep_version
                )
            )
        case _:
            return err("invalid_scope", "scope must be user, local, or all")


def _relevant_inventory_error(
    error: str, scope: str, roots: tuple[Path, ...], hosts: tuple[str, ...]
) -> bool:
    match tuple(error.split(":", 2)):
        case (host, path, _reason) if host and path and (not hosts or host in hosts):
            return path == "adapter" or scope != "local" or _inside(Path(path), roots)
        case _:
            return True


def _json_comments(text: str) -> str:
    return re.sub(
        r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*.*?\*/|^[ \t]*#[^\r\n]*',
        lambda match: match.group(0) if match.group(0).startswith('"') else "",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )


def _json_remove(
    value: Any,
    selectors: tuple[tuple[str | int, ...], ...],
    prefix: tuple[str | int, ...] = (),
) -> tuple[Any, int, bool]:
    match value:
        case dict() as mapping:
            kept = tuple(
                (key, item)
                for key, item in mapping.items()
                if prefix + (key,) not in selectors
            )
            removed = len(mapping) - len(kept)
            children = tuple(
                (key, _json_remove(item, selectors, prefix + (key,)))
                for key, item in kept
            )
            value = {
                key: child
                for key, (child, _, emptied) in children
                if not (emptied and child in ({}, []))
            }
            count = removed + sum(item[1][1] for item in children)
            return value, count, bool(count and not value)
        case list() as items:
            kept = tuple(
                (index, item)
                for index, item in enumerate(items)
                if prefix + (index,) not in selectors
            )
            children = tuple(
                _json_remove(item, selectors, prefix + (index,)) for index, item in kept
            )
            value = [
                child
                for child, _, emptied in children
                if not (emptied and child in ({}, []))
            ]
            count = len(items) - len(kept) + sum(item[1] for item in children)
            return value, count, bool(count and not value)
        case _:
            return value, 0, False


def _rewrite_json(
    text: str, selectors: tuple[tuple[str | int, ...], ...]
) -> Result[str]:
    try:
        value, count, _ = _json_remove(json.loads(_json_comments(text)), selectors)
        return (
            Ok(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            if count
            else err(
                "selector_not_found", "requested owned JSON selectors were not present"
            )
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return err("invalid_document", f"invalid JSON document: {exc}")


def _header_parts(value: str) -> tuple[str, ...]:
    return tuple(
        part.strip().strip('"')
        for part in re.split(r"\.(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", value)
    )


def _toml_headers(lines: list[str]) -> tuple[tuple[int, bool, tuple[str, ...]], ...]:
    return tuple(
        (
            index,
            found.group(1) == "[[",
            _header_parts((found.group(2) or found.group(5)).strip()),
        )
        for index, line in enumerate(lines)
        if (
            found := re.match(
                r"^\s*(?:(\[\[)([^\]]+)(\]\])|(\[)([^\]]+)(\]))\s*(?:#.*)?$", line
            )
        )
    )


def _rewrite_toml_tables(
    text: str, requested: tuple[tuple[str, ...], ...]
) -> Result[str]:
    lines = text.splitlines(keepends=True)
    headers = _toml_headers(lines)
    selected_arrays = tuple(
        header for _, array, header in headers if array and header in requested
    )
    spans = tuple(
        (
            start,
            headers[index + 1][0] if index + 1 < len(headers) else len(lines),
        )
        for index, (start, array, header) in enumerate(headers)
        if (
            not array
            or any(
                header[: len(path)] == path and len(path) < len(header)
                for path in requested
            )
        )
        and (
            header in requested
            or any(
                header[: len(path)] == path and len(path) < len(header)
                for path in requested
            )
        )
    )
    output = "".join(
        line
        for index, line in enumerate(lines)
        if not any(start <= index < end for start, end in spans)
    )
    match (selected_arrays, spans):
        case arrays, _ if arrays:
            return err(
                "unsupported_document", "TOML array-table cleanup is unsupported"
            )
        case _, ():
            return err(
                "selector_not_found", "requested owned TOML selectors were not present"
            )
        case _, _:
            try:
                tomllib.loads(output)
                return Ok(output)
            except tomllib.TOMLDecodeError as exc:
                return err(
                    "invalid_document", f"invalid TOML after table removal: {exc}"
                )


def _rewrite_toml(
    text: str, selectors: tuple[tuple[str | int, ...], ...]
) -> Result[str]:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return err("invalid_document", f"invalid TOML document: {exc}")
    requested = tuple(tuple(str(part) for part in selector) for selector in selectors)
    managed = ("__managed_block__",) in requested
    lines = text.splitlines(keepends=True)
    starts = tuple(
        index
        for index, line in enumerate(lines)
        if line
        in {
            "# BEGIN monolithic-dev-harness\n",
            "# >>> monolithic-dev-harness hooks (managed: install.sh --host kimi) >>>\n",
        }
    )
    ends = tuple(
        index
        for index, line in enumerate(lines)
        if line
        in {
            "# END monolithic-dev-harness\n",
            "# <<< monolithic-dev-harness hooks <<<\n",
        }
    )
    match (managed, starts, ends):
        case True, (start,), (end,) if start < end:
            block_headers = tuple(
                header for _, _, header in _toml_headers(lines[start + 1 : end])
            )
            remaining = tuple(
                path
                for path in requested
                if path != ("__managed_block__",)
                and not any(
                    path[: len(header)] == header or header[: len(path)] == path
                    for header in block_headers
                )
            )
            output = "".join(
                line for index, line in enumerate(lines) if not start <= index <= end
            )
            match remaining:
                case ():
                    try:
                        tomllib.loads(output)
                        return Ok(output)
                    except tomllib.TOMLDecodeError as exc:
                        return err(
                            "invalid_document",
                            f"invalid TOML after managed block removal: {exc}",
                        )
                case _:
                    return _rewrite_toml_tables(output, remaining)
        case True, _, _:
            return err(
                "invalid_document",
                "managed TOML block must have exactly one balanced marker pair",
            )
        case False, _, _:
            return _rewrite_toml_tables(text, requested)


def rewrite_document(
    text: str, suffix: str, selectors: tuple[tuple[str | int, ...], ...]
) -> Result[str]:
    match suffix.lower():
        case ".json" | ".jsonc":
            return _rewrite_json(text, selectors)
        case ".toml":
            return _rewrite_toml(text, selectors)
        case _:
            return err(
                "unsupported_document", "only JSON, JSONC, and TOML are supported"
            )
