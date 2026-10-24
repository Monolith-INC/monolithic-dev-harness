"""The common adapter interface for process messages and native event translation."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from core.result import Ok, Result, err
from harness import rules
from harness.process_messages import Context

# Provider selection belongs at the adapter boundary, never in harness policy.
PROVIDERS = {"codex": "host_adapters.codex_process"}


def _provider(host: str) -> Any:
    match PROVIDERS.get(host):
        case str() as name:
            return importlib.import_module(name)
        case _:
            return None


def cli_context(host: str, repo: Path, native_id: str | None = None) -> Result[Context]:
    match _provider(host):
        case None:
            return err(
                "unsupported_process_adapter",
                "this adapter has no verified process message channel",
            )
        case provider:
            return provider.cli_context(repo, native_id)


def before_tool(
    host: str, repo: Path, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    match _provider(host):
        case None:
            return None
        case provider:
            return provider.before_tool(repo, payload, call)


def event(
    host: str, name: str, repo: Path, payload: dict[str, Any]
) -> Result[tuple[bool, str | None]]:
    match _provider(host):
        case None:
            return Ok((False, None))
        case provider:
            return provider.event(repo, name, payload)


def is_subagent(host: str, payload: dict[str, Any]) -> bool:
    match _provider(host):
        case None:
            return False
        case provider:
            return provider.is_subagent(payload)


def default_host() -> str:
    return next((host for host in PROVIDERS if _provider(host).active()), "text")
