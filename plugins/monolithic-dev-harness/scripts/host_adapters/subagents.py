"""The one contract for starting and following subagents on an agent host.

A host is two things: `hosts/<host>.json`, checked against `config/host.schema.json`, declares
which subagent operations the harness can ask of it and why we believe that; the host adapter's
`subagents()` returns a `SubagentOps`, a record of functions, so an adapter that leaves one out
cannot be built.

`for_host` joins them and checks every answer. An operation the declaration says is unsupported
returns `unsupported_capability`, whatever the adapter does. A result that is not what the
contract promises, including an exception, becomes `invalid_host_result`: a host can never turn
a missing operation into a plausible success.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from core.result import Err, Ok, Result, attempt, bind, err, fmap
from core.schema import load_schema, validate

T = TypeVar("T")

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOSTS_ROOT = PLUGIN_ROOT / "hosts"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "host.schema.json"
OPERATIONS = ("start", "status", "follow_up", "cancel", "events")
# Host name -> the adapter module that implements its `subagents()`.
ADAPTERS = {
    "claude": "host_adapters.claude_adapter",
    "codex": "host_adapters.codex_adapter",
    "cursor": "host_adapters.cursor_adapter",
    "zed": "host_adapters.zed_adapter",
    "kimi": "host_adapters.kimi_adapter",
}


class Tier(str, Enum):
    """Vendor-neutral model strength; each host maps it to its own model."""

    CHEAP = "cheap"
    MID = "mid"
    STRONG = "strong"


class Activity(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    WAITING = "waiting"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class Source(str, Enum):
    """Who produced an event: the host itself, our adapter, or nobody can tell."""

    HOST = "host"
    ADAPTER = "adapter"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Brief:
    """What to start: the agent's role and prompt, where it works, and how strong it runs.

    `idempotency_key` makes a retried start return the same subagent instead of a second one.
    """

    role: str
    prompt: str
    project: Path
    tier: Tier
    effort: str
    idempotency_key: str
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class Handle:
    """A started subagent, as the host identifies it."""

    host: str
    thread_id: str


@dataclass(frozen=True)
class Status:
    handle: Handle
    activity: Activity


@dataclass(frozen=True)
class Event:
    source: Source
    kind: str
    dedup_key: str
    provider_event_id: str = ""


@dataclass(frozen=True)
class EventPage:
    """Events in order; `next_cursor` is `""` when there are no more."""

    events: tuple[Event, ...]
    next_cursor: str


@dataclass(frozen=True)
class SubagentOps:
    start: Callable[[Brief], Result[Handle]]
    status: Callable[[Handle], Result[Status]]
    follow_up: Callable[[Handle, str], Result[Handle]]
    cancel: Callable[[Handle], Result[Status]]
    events: Callable[[str], Result[EventPage]]


@dataclass(frozen=True)
class Claim:
    supported: bool
    level: str
    source: str
    caveat: str


@dataclass(frozen=True)
class Declaration:
    host: str
    product: str
    verified_on: str
    operations: Mapping[str, Claim]

    def supports(self, operation: str) -> bool:
        return self.operations[operation].supported


def unsupported(host: str, operation: str) -> Err:
    return err(
        "unsupported_capability",
        f"the harness cannot {operation.replace('_', ' ')} a subagent on {host} yet",
    )


def unsupported_ops(host: str) -> SubagentOps:
    """Every operation unsupported: the honest adapter until one is verified on the host."""
    return SubagentOps(
        start=lambda _brief: unsupported(host, "start"),
        status=lambda _handle: unsupported(host, "status"),
        follow_up=lambda _handle, _message: unsupported(host, "follow_up"),
        cancel=lambda _handle: unsupported(host, "cancel"),
        events=lambda _cursor: unsupported(host, "events"),
    )


# --- the declaration ------------------------------------------------------------------------


def declaration(host: str, root: Path = HOSTS_ROOT) -> Result[Declaration]:
    """`hosts/<host>.json`, checked against the schema and its own file name."""
    path = root / f"{host}.json"
    if host not in ADAPTERS or not path.is_file():
        return err(
            "unsupported_capability", f"no subagent declaration for host {host!r}"
        )
    return bind(
        attempt(
            lambda: json.loads(path.read_text(encoding="utf-8")),
            "invalid_host_declaration",
            f"could not read {path.name}",
            OSError,
            ValueError,
        ),
        lambda document: bind(
            load_schema(SCHEMA_PATH),
            lambda schema: bind(
                validate(schema, document, "host_declaration"),
                lambda valid: _declaration(host, valid),
            ),
        ),
    )


def _declaration(host: str, document: Mapping[str, Any]) -> Result[Declaration]:
    if document["host"] != host:
        return err(
            "invalid_host_declaration",
            f"{host}.json declares host {document['host']!r}",
        )
    return Ok(
        Declaration(
            host=host,
            product=document["product"],
            verified_on=document["verified_on"],
            operations={
                name: Claim(
                    supported=claim["supported"],
                    level=claim["provenance"]["level"],
                    source=claim["provenance"].get("source", ""),
                    caveat=claim["provenance"].get("caveat", ""),
                )
                for name, claim in document["subagents"].items()
            },
        )
    )


def capabilities(host: str) -> Result[Mapping[str, bool]]:
    """Which operations the host declares, without calling the host."""
    return fmap(
        declaration(host),
        lambda found: {name: found.supports(name) for name in OPERATIONS},
    )


# --- the checked operations -----------------------------------------------------------------


def for_host(host: str) -> Result[SubagentOps]:
    """The host's subagent operations, held to its declaration and to the contract."""
    return bind(
        declaration(host),
        lambda found: fmap(_adapter_ops(host), lambda ops: checked(found, ops)),
    )


def _adapter_ops(host: str) -> Result[SubagentOps]:
    def build() -> SubagentOps:
        ops = importlib.import_module(ADAPTERS[host]).subagents()
        if not isinstance(ops, SubagentOps):
            raise TypeError(f"{host} adapter did not return SubagentOps")
        return ops

    return attempt(
        build,
        "invalid_host_adapter",
        f"{host} subagent adapter",
        ImportError,
        AttributeError,
        TypeError,
    )


def checked(found: Declaration, ops: SubagentOps) -> SubagentOps:
    host = found.host

    def call(
        operation: str,
        action: Callable[[], Result[T]],
        problem: Callable[[T], str],
    ) -> Result[T]:
        if not found.supports(operation):
            return unsupported(host, operation)
        try:
            result = action()
        except (
            Exception
        ) as exc:  # an adapter's crash is data for the caller, never a success
            return _invalid(host, operation, f"{type(exc).__name__}: {exc}")
        match result:
            case Ok(value):
                reason = problem(value)
                return _invalid(host, operation, reason) if reason else result
            case Err():
                return result
            case _:
                return _invalid(host, operation, "the adapter returned no Result")

    return SubagentOps(
        start=lambda brief: call(
            "start",
            lambda: ops.start(brief),
            lambda value: _handle_problem(host, value),
        ),
        status=lambda handle: call(
            "status",
            lambda: ops.status(handle),
            lambda value: _status_problem(handle, value),
        ),
        follow_up=lambda handle, message: call(
            "follow_up",
            lambda: ops.follow_up(handle, message),
            lambda value: "" if value == handle else "it answered for another subagent",
        ),
        cancel=lambda handle: call(
            "cancel",
            lambda: ops.cancel(handle),
            lambda value: _status_problem(handle, value),
        ),
        events=lambda cursor: call(
            "events", lambda: ops.events(cursor), _events_problem
        ),
    )


def _invalid(host: str, operation: str, reason: str) -> Err:
    return err("invalid_host_result", f"{host} {operation}: {reason}")


def _handle_problem(host: str, value: object) -> str:
    match value:
        case Handle(host=named, thread_id=thread_id) if named == host and thread_id:
            return ""
        case Handle():
            return "the handle must name this host and a thread id"
        case _:
            return "it returned no handle"


def _status_problem(handle: Handle, value: object) -> str:
    match value:
        case Status(handle=answered, activity=Activity()) if answered == handle:
            return ""
        case Status(activity=Activity()):
            return "it answered for another subagent"
        case _:
            return "it returned no status"


def _events_problem(value: object) -> str:
    if not isinstance(value, EventPage) or not isinstance(value.next_cursor, str):
        return "it returned no event page"
    keys = [event.dedup_key for event in value.events if isinstance(event, Event)]
    if len(keys) != len(value.events):
        return "every event must be an Event"
    if not all(keys) or len(set(keys)) != len(keys):
        return "every event needs its own dedup key"
    if not all(isinstance(event.source, Source) for event in value.events):
        return "every event must say who produced it"
    return ""
