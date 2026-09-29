"""Reach a provider's MCP server over stdio.

An MCP transport owns one child process and reuses it for its lifetime. The long-lived workflow
gateway therefore shares one provider authentication session instead of launching a new server for
every tool call. Short-lived commands still clean their child up at process exit.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import select
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from functools import lru_cache
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
    """A transport backed by one lazily started stdio MCP server."""
    exchange = _shared_exchange(command, args, timeout)
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


class _PersistentExchange:
    """One serialized MCP connection, restarted after a provider failure."""

    def __init__(self, command: str, args: tuple[str, ...], timeout: float) -> None:
        self._command = command
        self._args = args
        self._timeout = timeout
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        atexit.register(self.close)

    def __call__(self, request: Mapping[str, Any]) -> Result[Mapping[str, Any]]:
        with self._lock:
            return self._exchange(request)

    def _exchange(self, request: Mapping[str, Any]) -> Result[Mapping[str, Any]]:
        deadline = time.monotonic() + self._timeout
        match self._process:
            case process if process is not None and process.poll() is None:
                return self._request(process, request, deadline)
            case _:
                return bind(
                    self._start(deadline),
                    lambda process: self._request(process, request, deadline),
                )

    def _start(self, deadline: float) -> Result[subprocess.Popen[bytes]]:
        started = attempt(
            lambda: subprocess.Popen(
                [
                    os.path.expandvars(self._command),
                    *(os.path.expandvars(arg) for arg in self._args),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            ),
            "provider_unavailable",
            "could not start the provider",
            OSError,
        )
        match started:
            case Ok(process):
                initialized = _initialize(process, deadline)
                match initialized:
                    case Ok():
                        self._process = process
                        return Ok(process)
                    case Err() as failure:
                        _stop(process)
                        return failure
            case Err() as failure:
                return failure

    def _request(
        self,
        process: subprocess.Popen[bytes],
        request: Mapping[str, Any],
        deadline: float,
    ) -> Result[Mapping[str, Any]]:
        result = bind(
            _send(process, request),
            lambda _: _receive(process, int(request["id"]), deadline),
        )
        match result:
            case Err():
                self.close()
            case Ok():
                pass
        return result

    def close(self) -> None:
        match self._process:
            case process if process is not None:
                self._process = None
                _stop(process)
            case _:
                pass


def persistent_exchange(
    command: str, args: tuple[str, ...], timeout: float = 30.0
) -> Exchange:
    """An exchange that initializes once and reuses its child for sequential calls."""
    return _PersistentExchange(command, args, timeout)


@lru_cache(maxsize=16)
def _shared_exchange(command: str, args: tuple[str, ...], timeout: float) -> Exchange:
    """Process-local pool shared by tracker and SCM adapters in the gateway."""
    return persistent_exchange(command, args, timeout)


def _session(
    process: subprocess.Popen[bytes], request: Mapping[str, Any], deadline: float
) -> Result[Mapping[str, Any]]:
    try:
        return bind(
            _initialize(process, deadline),
            lambda _: bind(
                _send(process, request),
                lambda _: _receive(process, int(request["id"]), deadline),
            ),
        )
    finally:
        _stop(process)


def _initialize(process: subprocess.Popen[bytes], deadline: float) -> Result[None]:
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
    return bind(
        _send(process, initialize),
        lambda _: bind(
            _receive(process, 1, deadline),
            lambda _: _send(process, initialized),
        ),
    )


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
