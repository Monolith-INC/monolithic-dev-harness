"""Central process message catalog: JSON-RPC 2.0, protocol version 1.

Adapters select these constructors; caller identity arrives separately from the adapter.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from core.result import Failure, Ok, Result, err
from harness.process_assignment import Assignment, decode_assignment

VERSION = 1


@dataclass(frozen=True)
class HumanReply:
    """Host-normalized human input; authority remains in the verified caller context."""

    presentation_id: str
    question: str
    answer: str
    transport: str

    def decision_tuple(self) -> tuple[str, str, str]:
        return self.presentation_id, self.answer, self.transport


# Sessionless integration reads share the catalog and bus interface, not process authority.
INTEGRATION_READS = frozenset(
    {
        "tracker_describe",
        "tracker_preflight",
        "tracker_get_work_item",
        "tracker_search_work_items",
        "tracker_list_children",
        "tracker_list_artifacts",
        "workflow_tracking_status",
    }
)


def integration_read(
    project: str, operation: str, arguments: dict, event_id: str
) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": event_id,
        "method": "integration.read",
        "params": {
            "version": VERSION,
            "project": project,
            "operation": operation,
            "arguments": arguments,
        },
    }


def decode_integration_read(message: Any, project: str) -> Result[tuple[str, dict]]:
    match message:
        case {
            "jsonrpc": "2.0",
            "id": str() as identifier,
            "method": "integration.read",
            "params": {
                "version": 1,
                "project": str() as named,
                "operation": str() as operation,
                "arguments": dict() as arguments,
            },
        } if identifier and named == project:
            match operation in INTEGRATION_READS:
                case True:
                    return Ok((operation, arguments))
                case False:
                    return err(
                        "gateway_read_only",
                        "Local gateway clients may only read; use the approved host gateway for writes.",
                    )
        case _:
            return err(
                "invalid_integration_message",
                "Integration read does not match the project and central catalog.",
            )


class ProcessStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


class Origin(str, Enum):
    HOST = "host"
    AGENT = "agent"


@dataclass(frozen=True)
class Context:
    adapter: str
    owner_id: str
    work_session_id: str


@dataclass(frozen=True)
class Request:
    method: str
    event_id: str
    process_id: str
    digest: str
    execution_id: str = ""
    revision: int = 0
    status: ProcessStatus = ProcessStatus.UNKNOWN
    origin: Origin = Origin.HOST
    assignment: Assignment | None = None


METHOD_FIELDS = {
    "process.register": frozenset(("process_id", "execution_id")),
    "process.status_update": frozenset(
        ("process_id", "execution_id", "status", "revision", "origin")
    ),
    "process.cancel": frozenset(("process_id", "revision")),
    "process.get": frozenset(("process_id",)),
    "process.list": frozenset(),
    "process.assign": frozenset(("process_id", "revision", "assignment")),
}
BASE_FIELDS = frozenset(("version", "context", "event_id"))


def _request(
    method: str, context: Context, process_id: str | None, event_id: str, **fields: Any
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": event_id,
        "method": method,
        "params": {
            "version": VERSION,
            "context": asdict(context),
            **({"process_id": process_id} if process_id is not None else {}),
            "event_id": event_id,
            **fields,
        },
    }


def register(
    context: Context, process_id: str, execution_id: str, event_id: str
) -> dict[str, Any]:
    return _request(
        "process.register", context, process_id, event_id, execution_id=execution_id
    )


def status_update(
    context: Context,
    process_id: str,
    execution_id: str,
    status: ProcessStatus,
    event_id: str,
    revision: int,
    origin: Origin = Origin.HOST,
) -> dict[str, Any]:
    return _request(
        "process.status_update",
        context,
        process_id,
        event_id,
        execution_id=execution_id,
        status=status.value,
        revision=revision,
        origin=origin.value,
    )


def cancel(
    context: Context, process_id: str, event_id: str, revision: int
) -> dict[str, Any]:
    return _request("process.cancel", context, process_id, event_id, revision=revision)


def assign(
    context: Context,
    process_id: str,
    assignment: Assignment,
    event_id: str,
    revision: int,
) -> dict[str, Any]:
    return _request(
        "process.assign",
        context,
        process_id,
        event_id,
        revision=revision,
        assignment=asdict(assignment),
    )


def valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def reply(event_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """One success envelope for typed local and serialized RPC bindings."""
    return {"jsonrpc": "2.0", "id": event_id, "result": result}


def valid_context(value: Any) -> bool:
    return isinstance(value, Context) and all(
        valid_text(item)
        for item in (value.adapter, value.owner_id, value.work_session_id)
    )


def decode(message: Any, context: Context) -> Result[Request]:
    match message:
        case {
            "jsonrpc": "2.0",
            "id": str() as event_id,
            "method": str() as method,
            "params": dict() as params,
        } if (
            set(message) == {"jsonrpc", "id", "method", "params"}
            and method in METHOD_FIELDS
            and valid_context(context)
            and set(params) == BASE_FIELDS | METHOD_FIELDS[method]
            and type(params.get("version")) is int
            and params["version"] == VERSION
            and params.get("context") == asdict(context)
            and valid_text(event_id)
            and params.get("event_id") == event_id
            and (method == "process.list" or valid_text(params.get("process_id")))
            and _valid_fields(method, params)
        ):
            return Ok(
                Request(
                    method,
                    event_id,
                    params.get("process_id", ""),
                    hashlib.sha256(
                        json.dumps(
                            message, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest(),
                    params.get("execution_id", ""),
                    params.get("revision", 0),
                    ProcessStatus(params.get("status", "unknown")),
                    Origin(params.get("origin", "host")),
                    decode_assignment(params["assignment"]).value
                    if method == "process.assign"
                    else None,
                )
            )
        case _:
            return err(
                "invalid_process_message",
                "message does not match the central process catalog or adapter context",
            )


def _valid_fields(method: str, params: dict[str, Any]) -> bool:
    match method:
        case "process.get" | "process.list":
            return True
        case "process.register":
            return valid_text(params.get("execution_id"))
        case "process.assign":
            return (
                type(params.get("revision")) is int
                and params["revision"] >= 0
                and isinstance(decode_assignment(params.get("assignment")), Ok)
            )
        case "process.cancel":
            return type(params.get("revision")) is int and params["revision"] >= 0
        case "process.status_update":
            return (
                valid_text(params.get("execution_id"))
                and type(params.get("revision")) is int
                and params["revision"] >= 0
                and isinstance(params.get("status"), str)
                and params["status"] in tuple(item.value for item in ProcessStatus)
                and isinstance(params.get("origin"), str)
                and params["origin"] in tuple(item.value for item in Origin)
            )
        case _:
            return False


def inspect_process(context: Context, process_id: str, event_id: str) -> dict[str, Any]:
    return _request("process.get", context, process_id, event_id)


def list_processes(context: Context, event_id: str) -> dict[str, Any]:
    return _request("process.list", context, None, event_id)


def rejection(message: Any, failure: Failure) -> dict[str, Any] | None:
    """Standard error response; notifications cannot mutate state or receive replies."""
    match message:
        case {"jsonrpc": "2.0", "method": str()} if "id" not in message:
            return None
        case {"jsonrpc": "2.0", "method": str() as method, "id": identifier} if (
            method not in METHOD_FIELDS
        ):
            return _error(identifier, -32601, failure)
        case {"jsonrpc": "2.0", "method": str(), "id": identifier}:
            return _error(
                identifier,
                -32602 if failure.code == "invalid_process_message" else -32000,
                failure,
            )
        case _:
            return _error(None, -32600, failure)


def _error(identifier: Any, code: int, failure: Failure) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": identifier
        if isinstance(identifier, (str, int)) and type(identifier) is not bool
        else None,
        "error": {"code": code, "message": failure.message, "data": failure.to_dict()},
    }
