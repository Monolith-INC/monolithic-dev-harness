"""Agent-host adapter utilities."""

from __future__ import annotations

import os
import sys

# Bare imports (policy, ...) need scripts/ on path when loaded as host_adapters.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from .claude_adapter import format_claude_decision, parse_claude_payload
from .cursor_adapter import format_cursor_decision, parse_cursor_payload

__all__ = [
    "format_claude_decision",
    "format_cursor_decision",
    "parse_claude_payload",
    "parse_cursor_payload",
]
