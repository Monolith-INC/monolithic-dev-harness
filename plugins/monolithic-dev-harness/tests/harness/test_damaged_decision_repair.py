"""A damaged decision record still holds work, and `decision repair` is the one way past it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions
from tests.harness.test_approval_scope import project
from tests.harness.test_decisions import CLI, native

DAMAGE = ("", "{", "{}", "[]", '{"id": "d1", "status": "pending"}')


def bash(repo: Path, command: str) -> str:
    return native(
        repo,
        "pre-tool",
        {
            "session_id": "native-a",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )


def repair(repo: Path, *scope: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "decision", "repair", "--repo", str(repo), *scope],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("project_wide", (True, False), ids=("project", "session"))
@pytest.mark.parametrize("text", DAMAGE)
def test_a_damaged_decision_is_repaired_without_an_answer(
    tmp_path: Path, text: str, project_wide: bool
) -> None:
    first, _ = project(tmp_path)
    # The refusal names the conversation's session; repair finds a damaged project-wide record too.
    scope = ("--session-id", first)
    folder = (
        tmp_path / decisions.RELATIVE_PATH
        if project_wide
        else decisions._path(tmp_path, first).value
    )
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.write_text(text, encoding="utf-8")

    refused = bash(tmp_path, "touch notes.txt")
    assert "decision-pending" in refused and "decision repair" in refused
    command = " ".join(
        (str(CLI), "decision", "repair", "--repo", str(tmp_path), *scope)
    )
    assert "deny" not in bash(tmp_path, command)

    assert repair(tmp_path, *scope).returncode == 0
    assert not folder.exists()
    (kept,) = folder.parent.glob("decision.damaged-*.json")
    assert kept.read_text(encoding="utf-8") == text
    assert "decision-pending" not in bash(tmp_path, "touch notes.txt")


def test_repair_refuses_a_readable_question(tmp_path: Path) -> None:
    first, _ = project(tmp_path)
    assert isinstance(
        decisions.begin(
            tmp_path,
            "d1",
            "Continue?",
            ("Continue", "Stop"),
            "chat",
            work_session_id=first,
        ),
        Ok,
    )
    assert repair(tmp_path, "--session-id", first).returncode != 0
    assert decisions.pending(tmp_path, first) is not None
