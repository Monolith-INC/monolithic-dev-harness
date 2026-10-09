"""Agent-host adapter utilities."""

from __future__ import annotations

import os
import sys

# Bare imports (policy, ...) need scripts/ on path when loaded as host_adapters.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from .claude_adapter import (
    claude_session_id,
    format_claude_decision,
    parse_claude_payload,
)
from .codex_adapter import codex_session_id, format_codex_decision, parse_codex_payload
from .cursor_adapter import (
    cursor_session_id,
    format_cursor_decision,
    parse_cursor_payload,
)
from .zed_adapter import format_zed_decision, parse_zed_payload, zed_session_id


def select_adapter(client: str):
    match client.strip().lower():
        case "cursor":
            return parse_cursor_payload, format_cursor_decision
        case "codex":
            return parse_codex_payload, format_codex_decision
        case "zed":
            return parse_zed_payload, format_zed_decision
        case _:
            return parse_claude_payload, format_claude_decision


def native_session_id(client: str, payload):
    match client.strip().lower():
        case "codex":
            return codex_session_id(payload)
        case "claude":
            return claude_session_id(payload)
        case "cursor":
            return cursor_session_id(payload)
        case "zed":
            return zed_session_id(payload)
        case _:
            return ""


__all__ = [
    "format_claude_decision",
    "format_codex_decision",
    "format_cursor_decision",
    "parse_claude_payload",
    "parse_codex_payload",
    "parse_cursor_payload",
    "select_adapter",
    "native_session_id",
]
