"""Reach a provider's MCP server: start it, ask one thing, read the answer, stop it.

One process per call keeps provider sign-in and lifetime out of the hooks and the gateway. Every
outcome is an `Ok`/`Err` value; the process handling below is the only place that catches
exceptions.
"""

from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from itertools import accumulate, chain
from typing import Any

from core.result import Err, Failure, Ok, Result, attempt, bind, err, value_or

from .contracts import Transport

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "monolithic-dev-harness", "version": "1.0.0"}
REQUEST_ID = 2
# The Azure DevOps server fences its replies as untrusted content: `<<id>> [UNTRUSTED ...] <<id>>`
# before the payload and `<</id>>` after it.
_MARKER_LINE = re.compile(
    r"^\s*<</?[^<>\n]*>>.*<</?[^<>\n]*>>\s*$|^\s*<</?[^<>\n]*>>\s*$"
)

Exchange = Callable[[Mapping[str, Any]], Result[Mapping[str, Any]]]


def mcp(command: str, args: tuple[str, ...], timeout: float = 30.0) -> Transport:
    """A transport that runs `command args` as a stdio MCP server for each call."""
    exchange = process_exchange(command, args, timeout)
    return lambda tool, arguments: call_tool(exchange, tool, arguments)


def unavailable(reason: str) -> Transport:
    return lambda tool, arguments: err("provider_unavailable", reason)


def call_tool(
    exchange: Exchange, tool: str, arguments: Mapping[str, Any]
) -> Result[Any]:
    request = {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": "tools/call",
        "params": {"name": tool, "arguments": dict(arguments)},
    }
    return bind(exchange(request), _tool_result)


def list_tools(exchange: Exchange) -> Result[tuple[Mapping[str, Any], ...]]:
    request = {"jsonrpc": "2.0", "id": REQUEST_ID, "method": "tools/list", "params": {}}
    return bind(exchange(request), _tool_list)


def _tool_list(response: Mapping[str, Any]) -> Result[tuple[Mapping[str, Any], ...]]:
    match response:
        case {"error": error}:
            return err("provider_error", str(error))
        case {"result": {"tools": list(tools)}}:
            return Ok(tuple(tool for tool in tools if isinstance(tool, dict)))
        case _:
            return Ok(())


def _tool_result(response: Mapping[str, Any]) -> Result[Any]:
    match response:
        case {"error": error}:
            return err("provider_error", str(error))
        case {"result": {"isError": True, **rest}}:
            return Err(failure_from_text(content_text(rest.get("content"))))
        case {"result": dict(result)}:
            return Ok(decode(content_text(result.get("content")), result))
        case _:
            return Ok({})


def content_text(content: Any) -> str:
    return (
        "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
        if isinstance(content, list)
        else ""
    )


def decode(text: str, fallback: Any) -> Any:
    """The JSON a reply carries, with any untrusted-content fence taken off; text if not JSON."""
    return (
        _json_or(text, lambda: _json_or(unfenced(text), lambda: text))
        if text
        else fallback
    )


def unfenced(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _MARKER_LINE.match(line))


def _json_or(text: str, otherwise: Callable[[], Any]) -> Any:
    match attempt(lambda: json.loads(text), "not_json", "reply", ValueError):
        case Ok(value):
            return value
        case Err():
            return otherwise()


def failure_from_text(text: str) -> Failure:
    match decode(text, text):
        case {"code": code, **rest} if code:
            return Failure(
                str(code), str(rest.get("message") or code), bool(rest.get("retryable"))
            )
        case _:
            return Failure("provider_error", text)


# --- the process edge -------------------------------------------------------------------------


def process_exchange(
    command: str, args: tuple[str, ...], timeout: float = 30.0
) -> Exchange:
    def exchange(request: Mapping[str, Any]) -> Result[Mapping[str, Any]]:
        return bind(
            attempt(
                lambda: subprocess.Popen(
                    [
                        os.path.expandvars(command),
                        *(os.path.expandvars(arg) for arg in args),
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                ),
                "provider_unavailable",
                "could not start the provider",
                OSError,
            ),
            lambda process: _session(process, request, time.monotonic() + timeout),
        )

    return exchange


def _session(
    process: subprocess.Popen[bytes], request: Mapping[str, Any], deadline: float
) -> Result[Mapping[str, Any]]:
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": dict(CLIENT_INFO),
        },
    }
    initialized = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    try:
        return bind(
            _send(process, initialize),
            lambda _: bind(
                _receive(process, 1, deadline),
                lambda _: bind(
                    _send(process, initialized),
                    lambda _: bind(
                        _send(process, request),
                        lambda _: _receive(process, int(request["id"]), deadline),
                    ),
                ),
            ),
        )
    finally:
        _stop(process)


def _send(process: subprocess.Popen[bytes], payload: Mapping[str, Any]) -> Result[None]:
    def write() -> None:
        process.stdin.write((json.dumps(payload) + "\n").encode())  # type: ignore[union-attr]
        process.stdin.flush()  # type: ignore[union-attr]

    return attempt(
        write,
        "provider_unavailable",
        "could not write to the provider",
        OSError,
        AttributeError,
    )


def _receive(
    process: subprocess.Popen[bytes], expected: int, deadline: float
) -> Result[Mapping[str, Any]]:
    """The next reply carrying `expected` as its id; other lines are skipped until the deadline.

    Chunks are read lazily and split into lines as they arrive, keeping only the unfinished
    line between chunks, so a large reply or a chatty server costs linear time and no nesting.
    """
    chunks = iter(lambda: _chunk(process, deadline - time.monotonic()), b"")
    buffers = accumulate(
        chunks, lambda state, chunk: _split(state[1] + chunk), initial=((), b"")
    )
    lines = chain.from_iterable(complete for complete, _ in buffers)
    replies = (_json_or(line.decode(errors="replace"), lambda: None) for line in lines)
    match next(
        (
            reply
            for reply in replies
            if isinstance(reply, dict) and reply.get("id") == expected
        ),
        None,
    ):
        case None:
            return err(
                "provider_timeout",
                "the provider did not answer in time",
                retryable=True,
            )
        case reply:
            return Ok(reply)


def _split(buffer: bytes) -> tuple[tuple[bytes, ...], bytes]:
    """The complete lines in a buffer, and the unfinished rest."""
    *complete, rest = buffer.split(b"\n")
    return tuple(complete), rest


def _chunk(process: subprocess.Popen[bytes], remaining: float) -> bytes:
    """Whatever the server has written, waiting at most `remaining` seconds; empty at the deadline or its end."""
    stream = process.stdout
    ready = attempt(
        lambda: select.select([stream], [], [], max(remaining, 0))[0],
        "unreadable",
        "read",
        OSError,
        ValueError,
        TypeError,
    )
    match ready:
        case Ok([_, *_]) if remaining > 0:
            return value_or(
                attempt(
                    lambda: os.read(stream.fileno(), 65536),
                    "unreadable",
                    "read",
                    OSError,
                ),
                b"",
            )  # type: ignore[union-attr]
        case _:
            return b""


def _stop(process: subprocess.Popen[bytes]) -> None:
    with suppress(OSError):
        process.kill()
    with suppress(OSError, subprocess.TimeoutExpired):
        process.wait(timeout=1)
    tuple(
        _close(stream)
        for stream in (process.stdin, process.stdout, process.stderr)
        if stream is not None
    )


def _close(stream: Any) -> None:
    with suppress(OSError):
        stream.close()
