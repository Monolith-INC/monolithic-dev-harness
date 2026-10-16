"""Planning exceptions are narrow; ordinary implementation remains governed."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        ("docs/planning/split.json", False, False),
        ("docs/planning/risks.yaml", False, False),
        ("docs/planning/capacity.yml", False, False),
        ("docs/planning/hours.csv", False, False),
        ("docs/planning/notes.txt", False, False),
        ("docs/planning/evidence/reply.jsonl", False, False),
        ("docs/planning/source.py", False, True),
        ("docs/planning/run.sh", False, True),
        ("docs/planning", True, True),
        ("docs/planning-other/draft.md", False, True),
        ("lib/source.dart", False, True),
        # The local tracker's tickets are backlog, never code.
        ("Tickets/Ready/draft-counts.md", False, False),
        ("Tickets/Ready/draft-counts.md.new", False, False),
    ],
)
def test_planning_documents_and_data_are_not_code_without_source_globs(
    path, tree, expected
):
    assert is_code(path, None, tree, "docs/planning") is expected


def test_explicit_source_globs_take_precedence():
    assert is_code("docs/planning/source.md", ["**/*.md"], planning="docs/planning")


@pytest.mark.parametrize(
    "command,expected",
    [
        # A variable assigned once to a plain path is that path.
        (
            "F=docs/planning/d.md && { cat <<'EOF'\nx\nEOF\n} > $F.tmp && mv $F.tmp $F",
            False,
        ),
        ("S=/tmp/scratch; mkdir -p $S; cat > $S/tasks.json <<'EOF'\n{}\nEOF\n", False),
        ('D="Tickets/Ready"; echo x > "$D/draft.md"', False),
        ("F=lib/a.dart; echo x > $F", True),
        ("F=lib/a.dart && echo x > ${F}", True),
        # Bound more than once, or by a loop, or from a command: it cannot be followed.
        ("F=docs/x.md; F=lib/a.dart; echo x > $F", True),
        ("for F in lib/a.dart; do echo x > $F; done", True),
        ("F=$(ls lib | head -1); echo x > $F", True),
    ],
)
def test_shell_variables_assigned_once_are_followed(tmp_path, command, expected):
    assert writes_code(command, tmp_path, None, "docs/planning") is expected


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
        "Breakdown",
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


def test_planning_completion_needs_no_work_session(tmp_path):
    ops, marker, artifact = receipt_fixture()
    with patch.object(
        hook_runtime.workflow_requirements,
        "linked_session",
        side_effect=AssertionError("work session requested"),
    ):
        assert isinstance(hook_runtime._receipt_route(ops, marker, (artifact,)), Ok)


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
    refused = verify(ops, replace(marker, title="Implement count"), artifact)
    assert (
        isinstance(refused, Err)
        and "title starts with `Breakdown`" in refused.failure.message
    )


def test_the_breakdown_task_is_titled_as_the_skill_names_it():
    """`atomic-tasks.md` titles it `Breakdown`; a longer title that starts so is accepted too."""
    ops, marker, artifact = receipt_fixture()
    for title in ("Breakdown", "Breakdown — Plan", "breakdown: counts"):
        assert isinstance(verify(ops, replace(marker, title=title), artifact), Ok)


def test_a_task_without_a_receipt_still_requires_its_storys_session(tmp_path):
    ops, marker, _ = receipt_fixture()
    with patch.object(
        hook_runtime.workflow_requirements, "linked_session", return_value=None
    ):
        assert hook_runtime._task_completion(tmp_path, ops, marker).is_denied()


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


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("patterns", [None, ["lib/**/*.dart"]])
def test_external_symlink_needs_code_context(tmp_path, absolute, patterns):
    from scripts.policy import CanonicalToolEvent
    from tests.settings_fixture import write_settings

    root = tmp_path / "project"
    root.mkdir()
    write_settings(root, artifacts_path="docs/planning")
    (root / "docs/planning").mkdir(parents=True)
    (tmp_path / "external.dart").write_text("source")
    (root / "docs/planning/draft.md").symlink_to(tmp_path / "external.dart")
    path = (
        str(root / "docs/planning/draft.md") if absolute else "docs/planning/draft.md"
    )
    with patch.object(hook_runtime.code_content, "patterns", return_value=patterns):
        assert hook_runtime._edits_code(
            CanonicalToolEvent(
                client="codex",
                tool_name="Edit",
                kind="edit",
                file_path=path,
                workspace_root=str(root),
            )
        )
    assert writes_code(f"echo x > {path}", root, patterns, "docs/planning")


@pytest.mark.parametrize("linked,denied", [("S1", False), ("OTHER", True)])
def test_task_completion_follows_its_storys_work_session(tmp_path, linked, denied):
    from scripts.policy import CanonicalToolEvent

    parent, item = (
        WorkItem("S1", "S1", "Story", WorkItemKind.USER_STORY, LogicalState.BACKLOG),
        WorkItem(
            "T1",
            "T1",
            "Build it",
            WorkItemKind.TASK,
            LogicalState.BACKLOG,
            parent_id="S1",
        ),
    )
    ops = SimpleNamespace(
        get_work_item=Mock(side_effect=lambda ref: Ok(parent if ref == "S1" else item)),
        list_artifacts=Mock(return_value=Ok(())),
    )
    with (
        patch.object(hook_runtime, "_enforced", return_value=True),
        patch.object(
            hook_runtime.registry, "open_selected", return_value=Ok(ops)
        ) as opened,
        patch.object(
            hook_runtime.workflow_requirements,
            "linked_session",
            side_effect=lambda _root, key: "WS-1" if key == linked else None,
        ),
        patch.object(hook_runtime.settings, "load", return_value={}),
    ):
        assert (
            hook_runtime._evaluate_completion(
                CanonicalToolEvent(
                    client="codex",
                    tool_name="update",
                    kind="other",
                    workspace_root=str(tmp_path),
                ),
                item.id,
            ).is_denied()
            is denied
        )
    opened.assert_called_once()
    ops.list_artifacts.assert_called_once_with(item.id)


def test_corrected_receipt_supersedes_prior_revision(tmp_path):
    ops, marker, receipt = receipt_fixture()
    old = replace(receipt, content="bad", revision="1")
    corrected = replace(receipt, id="A2", revision="2")
    assert isinstance(hook_runtime._receipt_route(ops, marker, (old, corrected)), Ok)
    assert isinstance(
        hook_runtime._receipt_route(
            ops, marker, (old, replace(corrected, revision="1"))
        ),
        Err,
    )


@pytest.mark.parametrize(
    "command,expected",
    [
        # Trial test-012: the sed script named a source file, and counted as the file edited.
        (
            "cd docs/planning && sed -i 's/(`lib\\/a.dart:68`)/(`lib\\/a.dart:67`)/' approach.md",
            False,
        ),
        ("sed -i -e 's/a/b/' docs/planning/approach.md", False),
        ("sed -i 's/a/b/' lib/a.dart", True),
        ("sed -i -e 's/a/b/' lib/a.dart", True),
        ("sed -i.bak 's/a/b/' docs/planning/approach.md lib/a.dart", True),
        # After `cd dir &&`, the write runs only in that folder; after `;` the `cd` may have failed.
        ("cd docs/planning && echo x > approach.md", False),
        ("cd docs/planning && true && echo x > approach.md", False),
        ("cd docs/planning; echo x > approach.md", True),
        ("cd docs/planning || true && echo x > approach.md", True),
    ],
)
def test_in_place_editor_script_is_not_a_file(tmp_path, command, expected):
    assert writes_code(command, tmp_path, None, "docs/planning") is expected
