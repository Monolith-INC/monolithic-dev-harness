"""Suspension must escape broken setup and restore enforcement without losing progress."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness import policies

PLUGIN = Path(__file__).resolve().parents[2]
HOOK = PLUGIN / "scripts/harness/hook.py"
CLI = PLUGIN / "bin/harness"


def invoke(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "policies", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    )


def hook(repo: Path, tool: str, arguments: dict[str, str]) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOK), "--host", "codex", "--event", "pre-tool"],
        cwd=repo,
        input=json.dumps(
            {"cwd": str(repo), "tool_name": tool, "tool_input": arguments}
        ),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return (
        json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else {}
    )


def test_broken_setup_can_suspend_and_resume_without_approval(tmp_path: Path) -> None:
    (tmp_path / ".harness").mkdir()
    settings = tmp_path / ".harness/settings.json"
    settings.write_text("invalid settings")
    checkpoint = tmp_path / ".harness/state/workflow.json"
    checkpoint.parent.mkdir()
    checkpoint.write_text('{"status":"paused","request":"keep me"}')
    edit = {"file_path": str(tmp_path / "app.py"), "content": "value = 1"}
    assert hook(tmp_path, "Write", edit)["permissionDecision"] == "deny"
    control = {"command": f"{CLI} policies suspend"}
    assert hook(tmp_path, "Bash", control).get("permissionDecision", "allow") == "allow"
    assert invoke(tmp_path, "suspend").returncode == 0
    assert invoke(tmp_path, "status").stdout.strip() == '{"mode": "suspended"}'
    assert hook(tmp_path, "Write", edit).get("permissionDecision", "allow") == "allow"
    assert checkpoint.read_text() == '{"status":"paused","request":"keep me"}'
    assert settings.read_text() == "invalid settings"
    assert invoke(tmp_path, "resume").returncode == 0
    assert hook(tmp_path, "Write", edit)["permissionDecision"] == "deny"


def test_suspend_before_setup_is_repository_local(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    assert invoke(first, "suspend").returncode == 0
    assert policies.suspended(first)
    assert not policies.suspended(second)
    assert not (first / ".harness/settings.json").exists()


def test_control_does_not_exempt_other_commands_or_projects(tmp_path: Path) -> None:
    assert policies.control_command(f"{CLI} policies suspend", tmp_path)
    assert not policies.control_command(f"{CLI} policies suspend && git push", tmp_path)
    assert not policies.control_command(
        f"{CLI} policies suspend --repo /another", tmp_path
    )


def test_named_control_on_path_is_available_with_broken_setup(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("PATH", str(CLI.parent))
    assert policies.control_command("harness policies suspend", tmp_path)


def test_suspended_mode_still_protects_control_records(tmp_path: Path) -> None:
    assert invoke(tmp_path, "suspend").returncode == 0
    decision = hook(
        tmp_path,
        "Write",
        {
            "file_path": str(tmp_path / policies.RELATIVE_PATH),
            "content": '{"mode":"active"}',
        },
    )
    assert decision["permissionDecision"] == "deny"


def test_unwritable_control_reports_failure(tmp_path: Path) -> None:
    (tmp_path / ".harness").write_text("a file, not a directory")
    result = invoke(tmp_path, "suspend")
    assert result.returncode != 0
    assert not policies.suspended(tmp_path)
