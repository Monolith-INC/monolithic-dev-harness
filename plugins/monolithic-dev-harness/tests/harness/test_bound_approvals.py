"""A gate's approval is tied to what the human reviewed and lasts until that changes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness import state, work_sessions
from tests.harness.test_approval_scope import WRITE, project
from tests.harness.test_decisions import CLI, native


def approve(repo: Path, session: str, native_id: str, gate: str, *args: str) -> dict:
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--session-id",
            session,
            "--gate",
            gate,
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    shown = json.loads(result.stdout)
    native(repo, "prompt", {"session_id": native_id, "prompt": "approve"})
    return shown


def tracker_write(repo: Path, native_id: str) -> str:
    return native(repo, "pre-tool", {**WRITE, "session_id": native_id})


def push(repo: Path, native_id: str, branch: str) -> str:
    return native(
        repo,
        "pre-tool",
        {
            "tool_name": "Bash",
            "tool_input": {"command": f"git push origin {branch}"},
            "session_id": native_id,
        },
    )


def test_a_publish_approval_holds_until_the_drafts_change(tmp_path: Path) -> None:
    first, _ = project(tmp_path)
    (tmp_path / "drafts.md").write_text("three stories")
    approve(
        tmp_path,
        first,
        "native-a",
        "publish-items",
        "--value",
        "count=3",
        "--value",
        "tracker=Azure Boards",
        "--artifact",
        "drafts.md",
    )
    ((_, record),) = state.open_approvals(tmp_path, first)
    assert "expires" not in record and record["binds"]["artifacts"]
    assert "deny" not in tracker_write(tmp_path, "native-a")
    (tmp_path / "drafts.md").write_text("four stories")
    denied = tracker_write(tmp_path, "native-a")
    assert "approval-required" in denied and "changed" in denied


def test_a_branch_approval_covers_only_that_branch(tmp_path: Path) -> None:
    first, _ = project(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "feat/x", str(tmp_path)], check=True)
    approve(tmp_path, first, "native-a", "publish-branch", "--value", "branch=feat/x")
    assert "deny" not in push(tmp_path, "native-a", "feat/x")
    assert "approval-required" in push(tmp_path, "native-a", "feat/y")
    assert "approval-required" in tracker_write(tmp_path, "native-a")


def test_an_approval_ends_with_its_work_session(tmp_path: Path) -> None:
    first, _ = project(tmp_path)
    (tmp_path / "drafts.md").write_text("three stories")
    approve(
        tmp_path,
        first,
        "native-a",
        "publish-items",
        "--value",
        "count=3",
        "--value",
        "tracker=Azure Boards",
        "--artifact",
        "drafts.md",
    )
    assert "deny" not in tracker_write(tmp_path, "native-a")
    work_sessions.transition(tmp_path, first, "stop")
    assert "deny" in tracker_write(tmp_path, "native-a")


def test_a_general_approval_is_still_a_short_window(tmp_path: Path) -> None:
    first, _ = project(tmp_path, minutes=20)
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "approve HB-GEN01"})
    ((_, record),) = state.open_approvals(tmp_path, first)
    assert "binds" not in record and "expires" in record


def test_a_story_approval_covers_only_that_item(tmp_path: Path) -> None:
    first, _ = project(tmp_path)
    approve(
        tmp_path,
        first,
        "native-a",
        "move-item",
        "--value",
        "item=Shared lists",
        "--value",
        "status=In Progress",
        "--value",
        "ref=42",
    )

    def update(ref: str) -> str:
        return native(
            tmp_path,
            "pre-tool",
            {
                "tool_name": WRITE["tool_name"],
                "tool_input": {"action": "update", "id": ref},
                "session_id": "native-a",
            },
        )

    assert "deny" not in update("42")
    assert "approval-required" in update("43")
    assert "approval-required" in tracker_write(tmp_path, "native-a")
