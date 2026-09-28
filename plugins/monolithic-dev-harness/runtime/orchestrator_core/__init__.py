"""Deterministic orchestrator for the backlog skills.

The runtime shares the harness's settings, tracker contract, and planning values, which live
under the plugin's `scripts/`; this is the one place that puts it on the import path.
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

__version__ = "0.1.0"
