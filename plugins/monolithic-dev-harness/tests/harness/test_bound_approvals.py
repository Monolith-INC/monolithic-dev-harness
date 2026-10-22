"""A gate's approval is tied to what the human reviewed and lasts until that changes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness import state, work_sessions
from tests.harness.test_approval_scope import WRITE, project
from tests.harness.test_decisions import CLI, native


def approve(repo: Path, session: str, native_id: str, gate: str, *args: str) -> dict:
    shown = [
        arg for flag, arg in zip(args, args[1:], strict=False) if flag == "--artifact"
    ]
    if shown:
        subprocess.run(
            [
                str(CLI),
                "workflow",
                "show",
                "--repo",
                str(repo),
                "--session-id",
                session,
                *(a for name in shown for a in ("--artifact", name)),
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
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


def test_marking_a_reviewed_draft_active_keeps_the_publish_approval(
    tmp_path: Path,
) -> None:
    first, _ = project(tmp_path)
    drafts = tmp_path / "drafts.md"
    drafts.write_text("---\nstatus: draft\n---\n\nthree stories\n")
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
    drafts.write_text("---\nstatus: active\n---\n\nthree stories\n")
    assert "deny" not in tracker_write(tmp_path, "native-a")
    drafts.write_text("---\nstatus: active\n---\n\nfour stories\n")
    assert "approval-required" in tracker_write(tmp_path, "native-a")


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


GATEWAY = "mcp__plugin_monolithic-dev-harness_workflow-integrations__"


def test_an_item_approval_does_not_cover_rewriting_its_content(tmp_path: Path) -> None:
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

    def gateway(tool: str, **arguments: object) -> str:
        return native(
            tmp_path,
            "pre-tool",
            {
                "tool_name": GATEWAY + tool,
                "tool_input": {"ref": "42", **arguments},
                "session_id": "native-a",
            },
        )

    assert "deny" not in gateway("tracker_transition_work_item", state="in_progress")
    assert "deny" not in gateway("tracker_update_work_item", hours=4)
    for content in ({"title": "New"}, {"description": "New"}, {"storyPoints": 3}):
        assert "approval-required" in gateway("tracker_update_work_item", **content)


def test_a_work_item_is_written_as_the_draft_the_user_approved(tmp_path: Path) -> None:
    """The toolkit's Gate 2: what reaches the tracker is the approved draft's body, word for
    word, even after creating the item replaced its draft in `Tickets/`."""
    first, _ = project(tmp_path)
    ready = tmp_path / "Tickets" / "Ready"
    ready.mkdir(parents=True)
    body = "## 🎯 What\n\nShow both counts.\n"
    for name, text in (
        ("draft-one.md", body),
        ("draft-two.md", "## 🎯 What\n\nOther.\n"),
    ):
        (ready / name).write_text(
            f"---\ntype: ticket\nwork_item_type: User Story\n---\n\n{text}"
        )
    approve(
        tmp_path,
        first,
        "native-a",
        "publish-items",
        "--value",
        "count=2",
        "--value",
        "tracker=Local tracker",
        "--artifact",
        "Tickets/Ready/draft-one.md",
        "--artifact",
        "Tickets/Ready/draft-two.md",
    )

    def create(description: str) -> str:
        return native(
            tmp_path,
            "pre-tool",
            {
                "tool_name": GATEWAY + "tracker_create_work_item",
                "tool_input": {
                    "kind": "user_story",
                    "title": "Counts",
                    "description": description,
                },
                "session_id": "native-a",
            },
        )

    assert "deny" not in create(body)
    assert "approved draft" in create("Show both counts, in my own words.")
    # Creating the first item replaced its draft; the second draft is still approved as it was.
    (ready / "draft-one.md").unlink()
    assert "deny" not in create("## 🎯 What\n\nOther.")
    (ready / "draft-two.md").write_text("---\ntype: ticket\n---\n\nChanged.\n")
    assert "approval-required" in create("Changed.")
