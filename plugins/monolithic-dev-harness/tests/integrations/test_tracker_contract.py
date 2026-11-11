"""The tracker base surface, the same scenario against every shipped adapter (Article 14).

Each adapter is built on its own provider's reply shapes (`trackers.py` holds the fakes for the
remote ones), so a scenario that passes here passes through the one neutral contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.result import Err, Ok
from integrations.contracts import TrackerOps, WorkItemChanges, WorkItemKind

from .fakes import ops

ADAPTERS = ["local"]


@pytest.fixture(params=ADAPTERS)
def tracker(request, tmp_path: Path) -> TrackerOps:
    match request.param:
        case "local":
            return ops("local", {}, repo=tmp_path)
    raise AssertionError(request.param)


def _story_under_feature(tracker: TrackerOps):
    feature = tracker.create_work_item(WorkItemKind.FEATURE, "F", "f", "").value
    story = tracker.create_work_item(
        WorkItemKind.USER_STORY, "S", "s", feature.key
    ).value
    return feature, story


def test_update_sets_tags_and_priority(tracker: TrackerOps) -> None:
    _, story = _story_under_feature(tracker)
    tracker.update_work_item(story.key, WorkItemChanges(tags=("api", "ux"), priority=2))
    read = tracker.get_work_item(story.key).value
    assert set(read.tags) == {"api", "ux"}
    assert read.priority == 2


def test_empty_tags_clear_them(tracker: TrackerOps) -> None:
    _, story = _story_under_feature(tracker)
    tracker.update_work_item(story.key, WorkItemChanges(tags=("api",)))
    tracker.update_work_item(story.key, WorkItemChanges(tags=()))
    assert tracker.get_work_item(story.key).value.tags == ()


def test_reparent_moves_the_item(tracker: TrackerOps) -> None:
    _, story = _story_under_feature(tracker)
    other = tracker.create_work_item(WorkItemKind.FEATURE, "G", "g", "").value
    assert isinstance(
        tracker.update_work_item(story.key, WorkItemChanges(parent=other.key)), Ok
    )
    assert tracker.get_work_item(story.key).value.parent_id == other.id


def test_reparent_under_a_forbidden_kind_is_refused(tmp_path: Path) -> None:
    local = ops("local", {}, repo=tmp_path)
    feature, story = _story_under_feature(local)
    second = local.create_work_item(
        WorkItemKind.USER_STORY, "T", "t", feature.key
    ).value
    before = local.get_work_item(story.key).value
    refused = local.update_work_item(story.key, WorkItemChanges(parent=second.key))
    assert isinstance(refused, Err) and refused.failure.code == "invalid_parent"
    assert local.get_work_item(story.key).value == before
