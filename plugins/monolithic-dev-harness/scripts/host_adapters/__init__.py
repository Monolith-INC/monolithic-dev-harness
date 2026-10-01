"""Agent-host adapter utilities."""

from __future__ import annotations

import os
import sys

# Bare imports (policy, ...) need scripts/ on path when loaded as host_adapters.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from .claude_adapter import format_claude_decision, parse_claude_payload
from .codex_adapter import format_codex_decision, parse_codex_payload
from .cursor_adapter import format_cursor_decision, parse_cursor_payload


def select_adapter(client: str):
    match client.strip().lower():
        case "cursor":
            return parse_cursor_payload, format_cursor_decision
        case "codex":
            return parse_codex_payload, format_codex_decision
        case _:
            return parse_claude_payload, format_claude_decision


__all__ = [
    "format_claude_decision",
    "format_codex_decision",
    "format_cursor_decision",
    "parse_claude_payload",
    "parse_codex_payload",
    "parse_cursor_payload",
    "select_adapter",
]
