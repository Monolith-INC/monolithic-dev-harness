"""Translate shared local installation into native project assets, without writing them."""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any

from core.result import Result, attempt, err

from .installation_contract import ProjectAsset

MARKER = "monolithic-dev-harness"
BEGIN = "# BEGIN monolithic-dev-harness\n"
END = "# END monolithic-dev-harness\n"
VARIABLES = ("${PLUGIN_ROOT}", "${CLAUDE_PLUGIN_ROOT}", "${CURSOR_PLUGIN_ROOT}")


def assets(host: str, project: Path, plugin: Path) -> Result[tuple[ProjectAsset, ...]]:
    match BUILDERS.get(host):
        case None:
            return err("unsupported_host", "host has no local installation translation")
        case build:
            return attempt(
                lambda: build(project.resolve(), plugin.resolve()),
                "invalid_project_configuration",
                "project assets could not be prepared",
                OSError,
                ValueError,
                TypeError,
                KeyError,
            )


def _replace(value: str, plugin: Path) -> str:
    return (
        value.replace(VARIABLES[0], str(plugin))
        .replace(VARIABLES[1], str(plugin))
        .replace(VARIABLES[2], str(plugin))
    )


def _expand(value: Any, plugin: Path, key: str = "") -> Any:
    match value:
        case dict() as mapping:
            return {name: _expand(item, plugin, name) for name, item in mapping.items()}
        case list() as items:
            return [_expand(item, plugin) for item in items]
        case str() as text if key == "command" and any(
            marker in text for marker in VARIABLES
        ):
            return shlex.join(
                tuple(_replace(word, plugin) for word in shlex.split(text))
            )
        case str() as text:
            return _replace(text, plugin)
        case _:
            return value


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _document(path: Path) -> dict:
    return _object(
        json.loads(
            re.sub(
                r'("(?:\\.|[^"\\])*")|(/\*[\s\S]*?\*/|//[^\r\n]*)',
                lambda match: match.group(1) or "",
                _read(path),
            )
            or "{}"
        )
    )


def _object(value: Any) -> dict:
    match value:
        case dict():
            return value
        case _:
            raise ValueError("configuration must contain a JSON object")


def _file(path: Path, document: dict) -> ProjectAsset:
    return ProjectAsset(
        path, "file", json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    )


def _owned(handler: dict) -> bool:
    return MARKER in str(
        handler.get("command", "")
    ) and "/scripts/harness/hook.py" in str(handler.get("command", ""))


def _retained(group: dict) -> tuple[dict, ...]:
    match group.get("hooks"):
        case list() as handlers:
            return (
                (
                    {
                        **group,
                        "hooks": [
                            handler for handler in handlers if not _owned(handler)
                        ],
                    },
                )
                if any(not _owned(handler) for handler in handlers)
                else ()
            )
        case _:
            return () if _owned(group) else (group,)


def _hook_asset(path: Path, source: Path, plugin: Path) -> ProjectAsset:
    current = _document(path)
    incoming = _expand(_document(source), plugin)
    return _file(
        path,
        {
            **current,
            **({"version": incoming["version"]} if "version" in incoming else {}),
            "hooks": {
                event: [
                    kept
                    for group in current.get("hooks", {}).get(event, [])
                    for kept in _retained(group)
                ]
                + incoming.get("hooks", {}).get(event, [])
                for event in dict.fromkeys(
                    (*current.get("hooks", {}), *incoming.get("hooks", {}))
                )
            },
        },
    )


def _mcp_asset(
    path: Path, source: Path, plugin: Path, key: str = "mcpServers"
) -> ProjectAsset:
    current = _document(path)
    incoming = _expand(_document(source), plugin)
    servers = incoming.get("mcpServers", incoming)
    return _file(
        path, {**current, key: _merge_servers(_object(current.get(key, {})), servers)}
    )


def _merge_servers(current: dict, incoming: dict) -> dict:
    match tuple(
        name
        for name in incoming
        if name in current and not _server_owned(current[name])
    ):
        case ():
            return {**current, **incoming}
        case conflicts:
            raise ValueError(
                f"unrelated MCP server names already exist: {', '.join(conflicts)}"
            )


def _server_owned(record: dict) -> bool:
    return (
        isinstance(record, dict)
        and record.get("command") in ("sh", "bash")
        and any(
            isinstance(value, str)
            and MARKER in Path(value).parts
            and value.endswith("/bin/harness-python")
            for value in record.get("args", ())
        )
    )


def _links(
    project: Path, plugin: Path, base: str, include_agents: bool = True
) -> tuple[ProjectAsset, ...]:
    return tuple(
        ProjectAsset(project / base / kind / source.name, "symlink", target=source)
        for kind in (("skills", "agents") if include_agents else ("skills",))
        for source in sorted((plugin / kind).iterdir())
        if source.is_dir() or source.suffix in (".md", ".toml")
    )


def _managed_toml(existing: str, block: str) -> str:
    match existing.count(BEGIN), existing.count(END):
        case 0, 0:
            return _valid_toml(
                existing
                + ("" if not existing or existing.endswith("\n") else "\n")
                + BEGIN
                + block
                + END
            )
        case 1, 1 if existing.index(BEGIN) < existing.index(END):
            return _valid_toml(
                existing.split(BEGIN, 1)[0]
                + BEGIN
                + block
                + END
                + existing.split(END, 1)[1]
            )
        case _:
            raise ValueError("ambiguous managed configuration block")


def _valid_toml(text: str) -> str:
    tomllib.loads(text)
    return text


def _server_block(servers: dict, plugin: Path) -> str:
    return "".join(
        "[mcp_servers."
        + json.dumps(name)
        + "]\n"
        + "".join(
            key + " = " + json.dumps(_expand(value, plugin)) + "\n"
            for key, value in server.items()
            if key != "env"
        )
        + "[mcp_servers."
        + json.dumps(name)
        + ".env]\n"
        + "".join(
            json.dumps(key) + " = " + json.dumps(_expand(value, plugin)) + "\n"
            for key, value in server.get("env", {}).items()
        )
        + "\n"
        for name, server in servers.items()
    )


def _claude(project: Path, plugin: Path) -> tuple[ProjectAsset, ...]:
    return (
        _hook_asset(
            project / ".claude/settings.local.json", plugin / "hooks/hooks.json", plugin
        ),
        _mcp_asset(project / ".mcp.json", plugin / ".mcp.json", plugin),
    ) + _links(project, plugin, ".claude")


def _cursor(project: Path, plugin: Path) -> tuple[ProjectAsset, ...]:
    return (
        _hook_asset(
            project / ".cursor/hooks.json", plugin / "hooks/cursor.hooks.json", plugin
        ),
        _mcp_asset(project / ".cursor/mcp.json", plugin / "cursor.mcp.json", plugin),
    ) + _links(project, plugin, ".cursor")


def _codex(project: Path, plugin: Path) -> tuple[ProjectAsset, ...]:
    return (
        (
            _hook_asset(
                project / ".codex/hooks.json", plugin / "hooks/codex.hooks.json", plugin
            ),
            ProjectAsset(
                project / ".codex/config.toml",
                "file",
                _managed_toml(
                    _read(project / ".codex/config.toml"),
                    _server_block(
                        _document(plugin / "codex.mcp.json")["mcpServers"], plugin
                    ),
                ),
            ),
        )
        + tuple(
            ProjectAsset(
                project / ".codex/agents" / name,
                "file",
                (plugin.parents[1] / "codex-marketplace/agents" / name).read_text(),
            )
            for name in ("mdh_thermo_review.toml", "mdh_thermo_quality.toml")
        )
        + _links(project, plugin, ".agents", False)
    )


def _kimi(project: Path, plugin: Path) -> tuple[ProjectAsset, ...]:
    return (
        _mcp_asset(project / ".kimi-code/mcp.json", plugin / "codex.mcp.json", plugin),
        ProjectAsset(
            project / ".kimi-code/config.toml",
            "file",
            _managed_toml(
                _read(project / ".kimi-code/config.toml"),
                "".join(
                    "[[hooks]]\nevent = "
                    + json.dumps(event)
                    + "\n"
                    + ("matcher = " + json.dumps(matcher) + "\n" if matcher else "")
                    + "command = "
                    + json.dumps(
                        shlex.join(
                            (
                                "sh",
                                str(plugin / "bin/harness-python"),
                                str(plugin / "scripts/harness/hook.py"),
                                "--host",
                                "kimi",
                                "--event",
                                operation,
                            )
                        )
                    )
                    + "\ntimeout = 15\n\n"
                    for event, matcher, operation in (
                        (
                            "PreToolUse",
                            "Shell|WriteFile|StrReplaceFile|mcp__.*",
                            "pre-tool",
                        ),
                        ("UserPromptSubmit", "", "prompt"),
                        ("Stop", "", "stop"),
                    )
                ),
            ),
        ),
    ) + _links(project, plugin, ".agents")


def _zed(project: Path, plugin: Path) -> tuple[ProjectAsset, ...]:
    return (
        _mcp_asset(
            project / ".zed/settings.json",
            plugin / "zed.mcp.json",
            plugin,
            "context_servers",
        ),
    )


BUILDERS = {
    "claude": _claude,
    "codex": _codex,
    "cursor": _cursor,
    "kimi": _kimi,
    "zed": _zed,
}
