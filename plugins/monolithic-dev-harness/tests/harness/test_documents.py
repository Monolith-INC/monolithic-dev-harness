"""Every document is named for its type and its work item, and filed under that item's folder."""

from __future__ import annotations

from pathlib import Path

from core.result import Ok, err
from harness import documents
from integrations.contracts import LogicalState, WorkItem, WorkItemKind

EPIC = WorkItem(
    "EPIC-0001", "EPIC-0001", "Daybook 2.0", WorkItemKind.EPIC, LogicalState.BACKLOG
)
FEATURE = WorkItem(
    "FEATURE-0002",
    "FEATURE-0002",
    "Task list insights",
    WorkItemKind.FEATURE,
    LogicalState.BACKLOG,
    parent_id="EPIC-0001",
)
STORY = WorkItem(
    "STORY-0003",
    "STORY-0003",
    "Show to-do and done task counts on the task screen",
    WorkItemKind.USER_STORY,
    LogicalState.BACKLOG,
    parent_id="FEATURE-0002",
)


class _Ops:
    def __init__(self, *items: WorkItem) -> None:
        self.items = {item.key: item for item in items}

    def get_work_item(self, ref: str):
        return Ok(self.items[ref]) if ref in self.items else err("not_found", ref)


def test_scope_names_the_item_as_the_toolkit_names_its_ticket_file() -> None:
    assert (
        documents.scope(STORY)
        == "user-story-0003-show-to-do-and-done-task-counts-on-the-task-screen"
    )
    azure = WorkItem(
        "6868", "6868", "Registro", WorkItemKind.FEATURE, LogicalState.READY
    )
    assert documents.scope(azure) == "feature-6868-registro"


def test_a_story_document_sits_under_its_feature_and_epic(tmp_path: Path) -> None:
    chain = documents.lineage(_Ops(EPIC, FEATURE, STORY), "STORY-0003").value
    assert chain == (EPIC, FEATURE, STORY)
    assert documents.item_path(tmp_path, chain, "spec") == (
        tmp_path
        / "epic-0001-daybook-2-0"
        / "feature-0002-task-list-insights"
        / "user-story-0003-show-to-do-and-done-task-counts-on-the-task-screen"
        / "spec-user-story-0003-show-to-do-and-done-task-counts-on-the-task-screen.md"
    )


def test_a_story_without_a_parent_sits_at_the_top(tmp_path: Path) -> None:
    alone = WorkItem(
        "STORY-0001",
        "STORY-0001",
        "Counts",
        WorkItemKind.USER_STORY,
        LogicalState.BACKLOG,
    )
    chain = documents.lineage(_Ops(alone), "STORY-0001").value
    assert documents.item_path(tmp_path, chain, "implementation-plan") == (
        tmp_path
        / "user-story-0001-counts"
        / "implementation-plan-user-story-0001-counts.md"
    )


def test_a_renamed_item_keeps_its_documents_folder(tmp_path: Path) -> None:
    """rc.10 trial: refinement retitled the Story, and its next document landed in a new folder
    beside the old one. Documents keep the name they started with (Article 8a)."""
    from dataclasses import replace

    before = WorkItem(
        "STORY-0001",
        "STORY-0001",
        "Show both task counts",
        WorkItemKind.USER_STORY,
        LogicalState.BACKLOG,
    )
    first = documents.item_path(tmp_path, (before,), "approach")
    first.parent.mkdir(parents=True)
    renamed = replace(
        before, title="Show active and completed task counts on the task screen"
    )
    assert documents.item_path(tmp_path, (renamed,), "implementation-plan") == (
        first.parent / "implementation-plan-user-story-0001-show-both-task-counts.md"
    )


def test_a_parent_loop_is_refused() -> None:
    loop = WorkItem(
        "STORY-0001",
        "STORY-0001",
        "Loop",
        WorkItemKind.USER_STORY,
        LogicalState.BACKLOG,
        parent_id="STORY-0001",
    )
    assert (
        "levels of parents"
        in documents.lineage(_Ops(loop), "STORY-0001").failure.message
    )


def _path(repo: Path, capsys, *argv: str) -> str:
    from harness import cli

    assert cli.main(["document", "path", "--repo", str(repo), *argv]) == 0
    return capsys.readouterr().out.strip()


def test_a_planned_item_is_named_with_the_number_it_will_get(
    tmp_path: Path, capsys
) -> None:
    from harness import settings
    from integrations import registry
    from tests.settings_fixture import write_settings

    write_settings(tmp_path, artifacts_path="docs/planning")
    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    feature = ops.create_work_item(WorkItemKind.FEATURE, "Insights", "Body", "").value
    new = ("--new", "user-story", "--title", "Show counts")

    spec = _path(tmp_path, capsys, *new, "--parent", feature.key, "--type", "spec")
    ticket = _path(tmp_path, capsys, *new, "--parent", feature.key, "--type", "ticket")
    assert spec == (
        "docs/planning/feature-0001-insights/user-story-0002-show-counts/"
        "spec-user-story-0002-show-counts.md"
    )
    assert ticket == "Tickets/Ready/0002-show-counts.md"

    draft = tmp_path / ticket
    draft.write_text("---\ntype: ticket\n---\n\nStory body\n", encoding="utf-8")
    # The reservation holds: the same title keeps its number, another takes the next one, and an
    # item created without a draft skips it.
    assert _path(tmp_path, capsys, *new, "--type", "ticket") == ticket
    other = _path(
        tmp_path, capsys, "--new", "user-story", "--title", "Other", "--type", "ticket"
    )
    assert other == "Tickets/Ready/0003-other.md"
    assert (
        ops.create_work_item(WorkItemKind.FEATURE, "Loose", "x", "").value.key
        == "FEATURE-0003"
    )

    story = ops.create_work_item(
        WorkItemKind.USER_STORY, "Show counts", "Story body", feature.key
    )
    assert story.value.key == "STORY-0002"
    # The ticket takes the draft's own file: nothing is renamed.
    assert 'provider_id: "STORY-0002"' in draft.read_text(encoding="utf-8")
    assert _path(tmp_path, capsys, "--item", "STORY-0002", "--type", "spec") == spec


def test_a_remote_tracker_names_documents_only_once_the_item_exists(
    tmp_path: Path,
) -> None:
    import argparse

    from tests.settings_fixture import write_settings

    write_settings(
        tmp_path,
        artifacts_path="docs/planning",
        tracker={"name": "linear", "values": {"team": "ENG"}},
    )
    args = argparse.Namespace(
        type="spec", item=None, new="user-story", title="Counts", parent=None
    )
    match documents.path(tmp_path, args):
        case result:
            assert "assigns an item's id when it is created" in result.failure.message


def test_story_is_read_as_user_story(tmp_path: Path, capsys) -> None:
    from tests.settings_fixture import write_settings

    write_settings(tmp_path, artifacts_path="docs/planning")
    assert _path(
        tmp_path, capsys, "--new", "story", "--title", "Counts", "--type", "spec"
    ) == ("docs/planning/user-story-0001-counts/spec-user-story-0001-counts.md")
