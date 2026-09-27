"""Test doubles: a transport that records calls and answers from a table, and tracker fixtures."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from core.result import Ok, Result, err
from integrations import registry
from integrations.contracts import AdapterContext, Manifest, TrackerOps

Answer = Any | Callable[[Mapping[str, Any]], Any]


class FakeTransport:
    """Answers each tool from `answers` (a value, or a function of the arguments) and records calls."""

    def __init__(self, answers: Mapping[str, Answer]):
        self.answers = dict(answers)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, tool: str, arguments: Mapping[str, Any]) -> Result[Any]:
        self.calls.append((tool, dict(arguments)))
        answer = self.answers.get(tool)
        if answer is None:
            return err("unexpected_tool", tool)
        return Ok(answer(arguments) if callable(answer) else answer)

    def sent(self, tool: str) -> list[dict[str, Any]]:
        return [arguments for name, arguments in self.calls if name == tool]


def shipped(name: str) -> Manifest:
    return registry.read_manifest(registry.SHIPPED_ROOT / name, "shipped").value


def ops(
    name: str,
    values: Mapping[str, str],
    call: FakeTransport | None = None,
    repo: Path = Path("."),
) -> TrackerOps:
    context = AdapterContext(
        shipped(name), MappingProxyType(dict(values)), repo, call or FakeTransport({})
    )
    return registry._adapter_function(context.manifest).value(context)


def module(name: str) -> Any:
    """The shipped adapter module itself, for its pure helper functions."""
    return registry._import(
        f"test_tracker_{name.replace('-', '_')}",
        registry.SHIPPED_ROOT / name / registry.ADAPTER,
    )


def copy_tracker(source: str, destination: Path, **changes: Any) -> Path:
    """A copy of a shipped tracker folder with manifest fields replaced."""
    shutil.copytree(
        registry.SHIPPED_ROOT / source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    manifest = json.loads((destination / "tracker.json").read_text())
    (destination / "tracker.json").write_text(json.dumps({**manifest, **changes}))
    return destination
