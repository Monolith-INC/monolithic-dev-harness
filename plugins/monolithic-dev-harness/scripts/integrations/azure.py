"""Compatibility import for the Azure tracker adapter.

The implementation moved to ``trackers/azure-devops/adapter.py``. This module remains during
the 0.1.x compatibility window so existing integrations and third-party imports keep working.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ADAPTER = (
    Path(__file__).resolve().parents[2] / "trackers" / "azure-devops" / "adapter.py"
)
_SPEC = importlib.util.spec_from_file_location("harness_tracker_azure_devops", _ADAPTER)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Azure tracker adapter is unavailable at {_ADAPTER}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
globals().update(
    {name: value for name, value in vars(_MODULE).items() if not name.startswith("_")}
)
