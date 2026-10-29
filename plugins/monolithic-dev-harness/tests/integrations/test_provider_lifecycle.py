"""Real provider failures retain their cause and do not relaunch OAuth on retry."""

import sys
import time
from pathlib import Path

from core.result import Err
from integrations import transport


def test_exit_is_not_a_retryable_timeout(tmp_path):
    failed = transport.mcp(
        sys.executable,
        ("-c", "import sys; print('secret-token',file=sys.stderr); sys.exit(7)"),
        2,
    )("read", {})
    assert failed.failure.code == "provider_exited"
    assert "7" in failed.failure.message
    assert "initialize" in failed.failure.message
    assert "secret-token" not in failed.failure.message
    assert not failed.failure.retryable


def test_failed_transport_does_not_automatically_restart(tmp_path):
    marker = tmp_path / "starts"
    exchange = transport.mcp(
        sys.executable,
        (
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).open('a').write('start\\n'); import time; time.sleep(5)",
        ),
        0.15,
    )
    assert isinstance(exchange("read", {}), Err)
    assert isinstance(exchange("read", {}), Err)
    assert marker.read_text().splitlines() == ["start"]


def test_timeout_cleans_up_launcher_descendant(tmp_path):
    marker = tmp_path / "child"
    failed = transport.mcp(
        sys.executable,
        (
            "-c",
            f"import subprocess,sys,time; from pathlib import Path; Path({str(marker)!r}).write_text(str(subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']).pid)); time.sleep(30)",
        ),
        0.3,
    )("read", {})
    assert failed.failure.code == "provider_timeout"
    time.sleep(0.05)
    assert (
        not Path(f"/proc/{marker.read_text()}/stat").exists()
        or Path(f"/proc/{marker.read_text()}/stat").read_text().split()[2] == "Z"
    )


def test_partial_desktop_context_is_completed_without_overwriting_explicit_values(
    monkeypatch,
):
    from integrations.desktop_environment import merge_desktop_environment

    assert merge_desktop_environment(
        {"DISPLAY": ":9", "PATH": "/bin"},
        "DISPLAY=:1\nDBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus\nTOKEN=private",
    ) == {
        "DISPLAY": ":9",
        "PATH": "/bin",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
    }


def test_installed_provider_launcher_needs_no_pythonpath(tmp_path, monkeypatch):
    from tests.integrations.test_transport import SERVER

    server = tmp_path / "server.py"
    server.write_text(SERVER)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    assert transport.mcp(sys.executable, (str(server),), 3)(
        "echo", {"reading": 1}
    ).value == {"reading": 1}
