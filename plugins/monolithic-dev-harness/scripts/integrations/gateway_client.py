"""Provider-neutral read clients; absent owner means recovery, never a second OAuth flow."""

from __future__ import annotations

import json
import os
import socket
import struct
import types
import typing
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.result import Err, Failure, Ok, Result, attempt, bind, err, fmap
from harness import state
from harness.process_messages import integration_read
from integrations.contracts import (
    ArtifactRef,
    LogicalState,
    Page,
    TrackerOps,
    WorkItem,
    WorkItemKind,
)
from integrations.planning import EstimableItem, IterationReading, Sprint


def call(repo: Path, operation: str, arguments: Mapping[str, Any]) -> Result[Any]:
    return bind(
        attempt(
            lambda: _exchange(repo, operation, dict(arguments)),
            "gateway_unavailable",
            "The host gateway is unavailable; reload/start workflow-integrations in this project, then retry this read. No provider was started.",
            OSError,
            ValueError,
            AttributeError,
        ),
        _result,
    )


def _exchange(repo: Path, operation: str, arguments: dict) -> dict:
    from .gateway_endpoint import MAX_MESSAGE, owner_record, private

    match state.read_json(owner_record(repo)):
        case {"endpoint": str() as recorded}:
            target = Path(recorded)
        case _:
            raise FileNotFoundError("No gateway owner is recorded for this project")
    match private(target.parent) and private(target):
        case False:
            raise PermissionError("Gateway endpoint is not private")
        case True:
            pass
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(65)
        connection.connect(str(target))
        match (
            struct.unpack(
                "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            ),
            state.read_json(owner_record(repo)),
        ):
            case (pid, uid, _), {
                "pid": int() as expected_pid,
                "uid": int() as expected_uid,
                "endpoint": str() as endpoint,
            } if (
                pid == expected_pid
                and uid == expected_uid == os.getuid()
                and endpoint == str(target)
            ):
                pass
            case _:
                raise PermissionError(
                    "Gateway peer does not match the protected owner record"
                )
        request = integration_read(
            str(repo.resolve()), operation, arguments, uuid4().hex
        )
        connection.sendall((json.dumps(request) + "\n").encode())
        with connection.makefile("rb") as response:
            match json.loads(response.readline(MAX_MESSAGE)):
                case {"id": str() as identifier} as value if (
                    identifier == request["id"]
                ):
                    return value
                case _:
                    raise ValueError("Gateway response does not match its request")


def _result(response: dict) -> Result[Any]:
    match response:
        case {
            "error": {
                "data": {"code": str() as code, "message": str() as message, **rest}
            }
        }:
            return Err(Failure(code, message, bool(rest.get("retryable"))))
        case {"result": value}:
            return Ok(value)
        case _:
            return err("invalid_gateway_reply", "Gateway returned an invalid response")


def _item(value: dict) -> WorkItem:
    return WorkItem(
        **{
            **value,
            "kind": WorkItemKind(value["kind"]),
            "state": LogicalState(value["state"]),
        }
    )


def _rebuilt(kind: Any, value: Any) -> Any:
    """A contract value from the JSON the gateway sent (`gateway.plain`): records, tuples, dates
    and optional fields rebuilt from the record's own type hints."""
    if value is None:
        return None
    if is_dataclass(kind):
        hints = typing.get_type_hints(kind)
        return kind(
            **{
                field.name: _rebuilt(hints[field.name], value[field.name])
                for field in fields(kind)
                if field.name in value
            }
        )
    origin, arguments = typing.get_origin(kind), typing.get_args(kind)
    if origin in (types.UnionType, typing.Union):
        return _rebuilt(next(a for a in arguments if a is not type(None)), value)
    if origin is tuple:
        return tuple(_rebuilt(arguments[0], item) for item in value)
    if kind is date:
        return date.fromisoformat(value)
    return value


def open_selected(active: Any, repo: Path) -> Result[TrackerOps]:
    from . import registry, transport

    return fmap(
        registry.build(
            active,
            repo,
            transport.unavailable(
                "Use the host gateway for external provider operations"
            ),
        ),
        lambda base: replace(
            base,
            get_work_item=lambda ref: fmap(
                call(repo, "tracker_get_work_item", {"ref": ref}), _item
            ),
            list_children=lambda ref: fmap(
                call(repo, "tracker_list_children", {"ref": ref}),
                lambda values: tuple(map(_item, values)),
            ),
            list_artifacts=lambda ref: fmap(
                call(repo, "tracker_list_artifacts", {"ref": ref}),
                lambda values: tuple(ArtifactRef(**value) for value in values),
            ),
            current_sprint=lambda: fmap(
                call(repo, "tracker_current_sprint", {}),
                lambda value: _rebuilt(Sprint, value),
            ),
            sprint_capacity=lambda sprint: fmap(
                call(repo, "tracker_sprint_capacity", {"sprint": sprint}),
                lambda value: _rebuilt(IterationReading, value),
            ),
            sprint_items=lambda sprint: fmap(
                call(repo, "tracker_sprint_items", {"sprint": sprint}),
                lambda values: tuple(
                    _rebuilt(EstimableItem, value) for value in values
                ),
            ),
            search_work_items=lambda query, cursor: fmap(
                call(
                    repo,
                    "tracker_search_work_items",
                    {"query": query, "cursor": cursor},
                ),
                lambda value: Page(
                    tuple(map(_item, value["items"])),
                    value["next_cursor"],
                    value["truncated"],
                ),
            ),
        ),
    )
