"""An item is judged on the text the tracker holds: Azure DevOps sends content HTML-escaped and
keeps a Story's points under `fields`."""

from __future__ import annotations

from typing import Any

from core.result import Err, Ok
from harness import refined
from integrations.contracts import LogicalState, WorkItem, WorkItemKind
from tests.harness.test_plan_review import REFINED

AZURE_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"
ESCAPED = REFINED.encode("ascii", "xmlcharrefreplace").decode("ascii")


def story(description: str, provider_data: dict[str, Any]) -> WorkItem:
    return WorkItem(
        "42",
        "42",
        "Explain what a settings reset removes",
        WorkItemKind.USER_STORY,
        LogicalState.READY,
        description=description,
        provider_data=provider_data,
    )


def test_a_story_in_the_template_with_points_is_refined() -> None:
    assert isinstance(refined.check(story(REFINED, {"story_points": 2})), Ok)


def test_azure_escaped_sections_are_read_as_written() -> None:
    assert "&#127919;" in ESCAPED
    assert isinstance(refined.check(story(ESCAPED, {"story_points": 2})), Ok)


def test_azure_story_points_are_read_from_its_fields() -> None:
    assert isinstance(refined.check(story(REFINED, {"fields": {AZURE_POINTS: 2}})), Ok)


def test_a_story_without_points_is_not_refined() -> None:
    assert isinstance(refined.check(story(REFINED, {"fields": {}})), Err)
