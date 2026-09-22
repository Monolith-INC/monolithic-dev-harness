from __future__ import annotations

import json
import os
import select
import subprocess
import time
from contextlib import suppress
from typing import Any

from .contracts import IntegrationError

_MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "codex-workflows-integrations", "version": "1.0.0"}


class StdioMcpClient:
    """Small dependency-free MCP client used by the integration gateway.

    The client intentionally starts one configured provider process per call. This
    keeps provider authentication and lifecycle outside the orchestrator and
    avoids leaking provider sessions into host hook processes.
    """

    def __init__(self, command: str, args: list[str], *, timeout: float = 30.0):
        self.command = command
        self.args = list(args)
        self.timeout = timeout

    def list_tools(self) -> list[dict[str, Any]]:
        """Negotiate initialize and return provider tool descriptors from tools/list."""
        response = self._roundtrip(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            expected_id=2,
        )
        if "error" in response:
            raise IntegrationError("provider_error", str(response["error"]))
        tools = (response.get("result") or {}).get("tools")
        if not isinstance(tools, list):
            return []
        return [tool for tool in tools if isinstance(tool, dict)]

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        response = self._roundtrip(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
            expected_id=2,
        )
        if "error" in response:
            error = response["error"]
            raise IntegrationError("provider_error", str(error))
        result = response.get("result") or {}
        if result.get("isError"):
            raise _integration_error_from_content(result.get("content"))
        return _decode_content(result.get("content"), result)

    def _roundtrip(
        self, request: dict[str, Any], *, expected_id: int
    ) -> dict[str, Any]:
        try:
            process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
            )
        except OSError as exc:
            raise IntegrationError(
                "provider_unavailable", f"Could not start provider tool: {exc}"
            ) from exc

        try:
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": _MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": dict(_CLIENT_INFO),
                    },
                },
            )
            self._read_response(process, 1)
            self._send(
                process,
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            )
            self._send(process, request)
            return self._read_response(process, expected_id)
        finally:
            with suppress(OSError):
                process.kill()
            with suppress(OSError, subprocess.TimeoutExpired):
                process.wait(timeout=1)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    with suppress(OSError):
                        stream.close()

    def _send(self, process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise IntegrationError(
                "provider_unavailable", "Provider stdin is unavailable."
            )
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()

    def _read_response(
        self, process: subprocess.Popen[str], expected_id: int
    ) -> dict[str, Any]:
        if process.stdout is None:
            raise IntegrationError(
                "provider_unavailable", "Provider stdout is unavailable."
            )
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                break
            line = process.stdout.readline()
            if not line:
                break
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") == expected_id:
                return payload
        raise IntegrationError(
            "provider_timeout",
            "Provider tool did not return a response in time.",
            retryable=True,
        )


def client_from_connection(connection: dict[str, Any]) -> StdioMcpClient:
    command = connection.get("command")
    args = connection.get("args", [])
    if not isinstance(command, str) or not command or not isinstance(args, list):
        raise IntegrationError(
            "invalid_config", "Provider connection requires command and args."
        )
    expanded_command = os.path.expandvars(command)
    expanded_args = [os.path.expandvars(str(item)) for item in args]
    return StdioMcpClient(
        expanded_command, expanded_args, timeout=float(connection.get("timeout", 30))
    )


def _decode_content(content: Any, fallback: Any) -> Any:
    text = _content_text(content)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return fallback


def _integration_error_from_content(content: Any) -> IntegrationError:
    text = _content_text(content)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return IntegrationError("provider_error", text)
    if isinstance(payload, dict) and payload.get("code"):
        return IntegrationError(
            str(payload["code"]),
            str(payload.get("message") or payload["code"]),
            retryable=bool(payload.get("retryable")),
        )
    return IntegrationError("provider_error", text)


def _content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )
