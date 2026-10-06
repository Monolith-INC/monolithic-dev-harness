"""`bin/harness-python` runs the harness on Python 3.12+, whatever `python3` is."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
LAUNCHER = PLUGIN / "bin" / "harness-python"


def interpreter(folder: Path, name: str, version: tuple[int, int]) -> Path:
    """A stand-in Python: answers the launcher's version check and reports who ran."""
    path = folder / name
    newer = "0" if version >= (3, 12) else "1"
    path.write_text(
        f'#!/bin/sh\nif [ "$1" = "-c" ]; then exit {newer}; fi\necho "{name} $*"\n'
    )
    path.chmod(0o755)
    return path


def launch(folder: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(LAUNCHER), "hook.py", "--event", "pre-tool"],
        env={"PATH": str(folder), **env},
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_a_versioned_interpreter_wins_over_an_old_python3(tmp_path: Path) -> None:
    interpreter(tmp_path, "python3", (3, 10))
    interpreter(tmp_path, "python3.12", (3, 12))
    interpreter(tmp_path, "python3.13", (3, 13))
    result = launch(tmp_path)
    assert result.stdout.strip() == "python3.13 hook.py --event pre-tool"


def test_a_new_enough_python3_is_used(tmp_path: Path) -> None:
    interpreter(tmp_path, "python3", (3, 12))
    assert launch(tmp_path).stdout.startswith("python3 hook.py")


def test_harness_python_is_honoured_when_new_enough(tmp_path: Path) -> None:
    interpreter(tmp_path, "python3.13", (3, 13))
    chosen = interpreter(tmp_path, "custom", (3, 12))
    assert launch(tmp_path, HARNESS_PYTHON=str(chosen)).stdout.startswith("custom ")
    old = interpreter(tmp_path, "old", (3, 11))
    interpreter(tmp_path, "python3", (3, 12))
    assert launch(tmp_path, HARNESS_PYTHON=str(old)).stdout.startswith("python3 ")


def test_no_new_enough_python_is_a_clear_failure(tmp_path: Path) -> None:
    interpreter(tmp_path, "python3", (3, 10))
    result = launch(tmp_path)
    assert result.returncode == 2
    assert "needs Python 3.12 or newer" in result.stderr
    assert result.stdout == ""


def test_the_installer_recorded_python_comes_first(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    (plugin / "bin").mkdir(parents=True)
    (plugin / "runtime").mkdir()
    launcher = plugin / "bin" / "harness-python"
    launcher.write_text(LAUNCHER.read_text())
    path_bin = tmp_path / "path"
    path_bin.mkdir()
    interpreter(path_bin, "python3.13", (3, 13))
    recorded = interpreter(tmp_path, "recorded", (3, 12))
    (plugin / "runtime" / "python-path").write_text(f"{recorded}\n")
    result = subprocess.run(
        ["/bin/sh", str(launcher), "hook.py"],
        env={"PATH": str(path_bin)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.stdout.startswith("recorded ")


@pytest.mark.parametrize("event", ["prompt", "ask", "answer"])
def test_without_python_the_users_message_still_goes_through(
    tmp_path: Path, event: str
) -> None:
    interpreter(tmp_path, "python3", (3, 10))
    result = subprocess.run(
        ["/bin/sh", str(LAUNCHER), "hook.py", "--host", "claude", "--event", event],
        env={"PATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "needs Python 3.12 or newer" in result.stderr


@pytest.mark.parametrize(
    "config", ["hooks/hooks.json", "hooks/codex.hooks.json", "hooks/cursor.hooks.json"]
)
def test_every_hook_starts_through_the_launcher(config: str) -> None:
    commands = [
        hook["command"]
        for groups in json.loads((PLUGIN / config).read_text())["hooks"].values()
        for group in groups
        for hook in group.get("hooks", [group])
    ]
    assert commands
    assert all(
        command.startswith("sh ") and "/bin/harness-python" in command
        for command in commands
    ), commands


@pytest.mark.parametrize("config", [".mcp.json", "codex.mcp.json", "cursor.mcp.json"])
def test_every_mcp_server_starts_through_the_launcher(config: str) -> None:
    servers = json.loads((PLUGIN / config).read_text())["mcpServers"].values()
    for server in servers:
        assert server["command"] == "sh"
        assert server["args"][0].endswith("/bin/harness-python")


@pytest.mark.parametrize("wrapper", ["harness", "agile-backlog-toolkit"])
def test_cli_wrappers_start_through_the_launcher(wrapper: str) -> None:
    text = (PLUGIN / "bin" / wrapper).read_text()
    assert "bin/harness-python" in text
    assert "exec python3" not in text


def test_no_skill_runs_plugin_scripts_with_bare_python() -> None:
    offenders = [
        f"{path.relative_to(PLUGIN)}:{number}"
        for path in (PLUGIN / "skills").glob("*/SKILL.md")
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if "<plugin root>/scripts/" in line and "harness-python" not in line
    ]
    assert offenders == []
