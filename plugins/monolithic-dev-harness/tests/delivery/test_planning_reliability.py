"""Planning exceptions are narrow; ordinary implementation remains governed."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.result import Err, Ok
from integrations.contracts import ArtifactRef, LogicalState, WorkItem, WorkItemKind
from policy.planning_completion import verify
from scripts import hook_runtime
from scripts.policy.commands import is_code, writes_code


@pytest.mark.parametrize(
    "path,tree,expected",
    [
        ("docs/planning/Tickets/draft.md", False, False),
        ("docs/planning/source.py", False, True),
        ("docs/planning", True, True),
        ("docs/planning-other/draft.md", False, True),
        ("lib/source.dart", False, True),
    ],
)
def test_planning_markdown_is_not_code_without_source_globs(path, tree, expected):
    assert is_code(path, None, tree, "docs/planning") is expected


def test_explicit_source_globs_take_precedence():
    assert is_code("docs/planning/source.md", ["**/*.md"], planning="docs/planning")


def test_shell_planning_write_and_source_write_are_distinct(tmp_path):
    assert not writes_code(
        "echo x > docs/planning/draft.md", tmp_path, None, "docs/planning"
    )
    assert writes_code("echo x > lib/source.dart", tmp_path, None, "docs/planning")


def receipt_fixture():
    parent = WorkItem(
        "S1", "S1", "Story", WorkItemKind.USER_STORY, LogicalState.BACKLOG
    )
    marker = WorkItem(
        "T2",
        "T2",
        "Breakdown — Plan",
        WorkItemKind.TASK,
        LogicalState.BACKLOG,
        parent_id="S1",
    )
    coding = WorkItem(
        "T1", "T1", "Build it", WorkItemKind.TASK, LogicalState.BACKLOG, parent_id="S1"
    )
    artifact = ArtifactRef(
        "A1",
        "planning_completion",
        "Published breakdown",
        "1",
        content=json.dumps(
            {
                "purpose": "breakdown",
                "item_id": "T2",
                "parent_id": "S1",
                "children": ["T1"],
            }
        ),
    )
    ops = SimpleNamespace(
        get_work_item=lambda _: Ok(parent), list_children=lambda _: Ok((coding, marker))
    )
    return ops, marker, artifact


def test_planning_completion_needs_no_checkout_session(tmp_path):
    ops, marker, artifact = receipt_fixture()
    with patch.object(
        hook_runtime,
        "_session_item",
        side_effect=AssertionError("implementation session requested"),
    ):
        assert isinstance(
            hook_runtime._completion_route(
                tmp_path, ops, marker, marker.id, (artifact,)
            ),
            Ok,
        )


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        "bad-json",
        json.dumps(
            {
                "purpose": "breakdown",
                "item_id": "other",
                "parent_id": "S1",
                "children": ["T1"],
            }
        ),
        json.dumps(
            {"purpose": "breakdown", "item_id": "T2", "parent_id": "S1", "children": []}
        ),
        json.dumps(
            {
                "purpose": "breakdown",
                "item_id": "T2",
                "parent_id": "S1",
                "children": ["missing"],
            }
        ),
        json.dumps(
            {
                "purpose": "breakdown",
                "item_id": "T2",
                "parent_id": "S1",
                "children": ["T1", "T1"],
            }
        ),
    ],
)
def test_incomplete_or_mismatched_completion_receipts_are_denied(content):
    ops, marker, artifact = receipt_fixture()
    assert isinstance(verify(ops, marker, replace(artifact, content=content)), Err)


def test_coding_task_cannot_use_planning_receipt():
    ops, marker, artifact = receipt_fixture()
    assert isinstance(
        verify(ops, replace(marker, title="Implement count"), artifact), Err
    )


def test_implementation_completion_still_requires_session(tmp_path):
    ops, marker, _ = receipt_fixture()
    with patch.object(
        hook_runtime,
        "_session_item",
        return_value=Err(hook_runtime._failure("missing session")),
    ):
        assert isinstance(
            hook_runtime._completion_route(tmp_path, ops, marker, marker.id, ()), Err
        )


def test_both_workflow_validator_tools_use_the_critic(tmp_path):
    from pathlib import Path

    from scripts.orchestrator.engine import OrchestratorEngine

    skills = Path(__file__).resolve().parents[2] / "skills"
    (tmp_path / "draft.md").write_text(
        "---\ntype: user_story\ntitle: Count tasks\n---\nMissing criteria."
    )
    with patch(
        "builtins.input",
        side_effect=AssertionError("implementation approval requested"),
    ):
        for name in ("validate-artifact", "auto-fix-artifact"):
            result = OrchestratorEngine(
                skills, interactive=True, quiet=True
            ).run_tool_call(
                name,
                {
                    "file_path": str(tmp_path / "draft.md"),
                    "draft_content": "---\ntype: user_story\ntitle: Count tasks\n---\nMissing criteria.",
                    "record_mistake": False,
                },
            )
            assert result.ok, result.error
            assert result.output["report"]
            assert result.output["critiques"]


def test_markdown_symlink_to_source_is_not_a_planning_edit(tmp_path):
    from scripts.policy import CanonicalToolEvent
    from tests.settings_fixture import write_settings

    write_settings(tmp_path, artifacts_path="docs/planning")
    (tmp_path / "docs/planning").mkdir(parents=True)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/source.dart").write_text("code")
    (tmp_path / "docs/planning/draft.md").symlink_to(tmp_path / "lib/source.dart")
    assert hook_runtime._edits_code(
        CanonicalToolEvent(
            client="codex",
            tool_name="Edit",
            kind="edit",
            file_path="docs/planning/draft.md",
            workspace_root=str(tmp_path),
        )
    )


def test_shell_symlink_to_source_needs_code_context(tmp_path):
    (tmp_path / "docs/planning").mkdir(parents=True)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/source.dart").write_text("source")
    (tmp_path / "docs/planning/draft.md").symlink_to(tmp_path / "lib/source.dart")
    assert writes_code(
        "echo x > docs/planning/draft.md", tmp_path, None, "docs/planning"
    )


def test_corrected_receipt_supersedes_prior_revision(tmp_path):
    ops, marker, receipt = receipt_fixture()
    old = replace(receipt, content="bad", revision="1")
    corrected = replace(receipt, id="A2", revision="2")
    assert isinstance(
        hook_runtime._completion_route(
            tmp_path, ops, marker, marker.id, (old, corrected)
        ),
        Ok,
    )
    assert isinstance(
        hook_runtime._completion_route(
            tmp_path, ops, marker, marker.id, (old, replace(corrected, revision="1"))
        ),
        Err,
    )
