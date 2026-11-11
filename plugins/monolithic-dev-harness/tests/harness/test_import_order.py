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
    ["harness.rules", "integrations.gateway", "integrations.run_gateway"],
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


@pytest.mark.parametrize(
    "module",
    ["harness.modes", "harness.mode_hooks", "host_adapters.work_session_context"],
)
def test_the_mode_modules_leave_the_gateway_unloaded(module: str) -> None:
    """The gateway imports the rule chain, which imports the mode modules. `modes` therefore loads
    the gateway only when it checks a manifest, and importing a mode module first, or the host
    adapter that now imports `modes`, must not load it. Importing it eagerly breaks the cycle for
    every importer that reaches the rules first, and only some of them are caught above."""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([".", "scripts"])}

    done = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import {module}, sys; "
            "assert 'integrations.gateway' not in sys.modules, 'the gateway was loaded'",
        ],
        cwd=PLUGIN_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert done.returncode == 0, done.stderr
