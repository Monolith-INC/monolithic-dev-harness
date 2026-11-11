"""Each module that starts a process imports cleanly as the first import of a fresh interpreter.

Every other test imports `harness` first, which happens to be an order that works. The gateway
entry point (`run_gateway.py`) and any importer that reaches `harness.rules` or
`integrations.gateway` first do not get that luck, so each runs here in a process of its own.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module",
    [
        "harness.rules",
        "integrations.gateway",
        "integrations.run_gateway",
        "host_adapters.work_session_context",
    ],
)
def test_the_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([".", "scripts"])}

    done = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=PLUGIN_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert done.returncode == 0, done.stderr
