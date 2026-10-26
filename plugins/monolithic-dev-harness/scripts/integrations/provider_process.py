"""Owned subprocess effects: supervision, bounded diagnostics and process-group shutdown."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from collections import deque
from contextlib import suppress
from pathlib import Path

# The installed launcher is executed by filename, outside any source checkout/PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.result import Ok, Result, attempt
from integrations.desktop_environment import provider_environment


def launch(command: str, args: tuple[str, ...]) -> subprocess.Popen:
    match shutil.which(command):
        case None:
            raise FileNotFoundError("Provider command is unavailable")
        case _:
            pass
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), command, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=provider_environment(),
        start_new_session=True,
    )
    process.diagnostics = deque(maxlen=8)
    process.stderr_thread = threading.Thread(
        target=_drain, args=(process,), daemon=True
    )
    process.stderr_thread.start()
    return process


def _drain(process: subprocess.Popen) -> deque:
    return deque(
        (
            process.diagnostics.append(chunk)
            for chunk in iter(lambda: process.stderr.read1(1024), b"")
        ),
        maxlen=0,
    )


def close(process: subprocess.Popen) -> Result[int]:
    with suppress(OSError, ValueError):
        process.stdin.close()
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=0.3)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=1)
    process.stderr_thread.join(timeout=0.3)
    tuple(
        stream.close()
        for stream in (process.stdin, process.stdout, process.stderr)
        if stream is not None
    )
    return Ok(process.returncode)


def diagnostic_summary(process: subprocess.Popen) -> str:
    return (
        "stderr observed"
        if bool(getattr(process, "diagnostics", ()))
        else "no stderr observed"
    )


def _forward(process: subprocess.Popen) -> Result[int]:
    # A side-effect boundary: stdin EOF means the owning gateway disappeared or closed.
    with suppress(OSError, ValueError):
        deque(
            (
                _write(process, chunk)
                for chunk in iter(lambda: os.read(sys.stdin.fileno(), 65536), b"")
            ),
            maxlen=0,
        )
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=0.3)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1)
    return Ok(0)


def _write(process: subprocess.Popen, chunk: bytes) -> int:
    process.stdin.write(chunk)
    process.stdin.flush()
    return len(chunk)


def main() -> int:
    match attempt(
        lambda: subprocess.Popen(
            sys.argv[1:], stdin=subprocess.PIPE, start_new_session=True
        ),
        "provider_unavailable",
        "Provider command could not start",
        OSError,
    ):
        case Ok(process):
            threading.Thread(target=_forward, args=(process,), daemon=True).start()
            return process.wait()
        case _:
            return 127


if __name__ == "__main__":
    raise SystemExit(main())
