"""Event-sourced skill orchestration scaffold (MCP tools/list + queue reducers)."""

from __future__ import annotations

import os
import sys

# Bare packages under scripts/ (policy, artifact_profiles, …) need scripts/ on path
# when this package is loaded via `python -m scripts.orchestrator` (REPO_ROOT only).
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from .engine import OrchestratorEngine, ToolCallResult

__all__ = ["OrchestratorEngine", "ToolCallResult"]
