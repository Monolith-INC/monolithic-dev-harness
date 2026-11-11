"""The tracker base surface, the same scenario against every shipped adapter (Article 14).

Each adapter is built on its own provider's reply shapes (`trackers.py` holds the fakes for the
remote ones), so a scenario that passes here passes through the one neutral contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.result import Err, Ok
from integrations.contracts import TrackerOps, WorkItemChanges, WorkItemKind

from .fakes import FakeTransport, ops
from .trackers import AzureBoard, LinearWorkspace

ADAPTERS = ["local", "azure-devops", "linear"]
AZURE = {"organization": "o", "project": "proj"}
LINEAR = {"team": "ENG"}


@pytest.fixture(params=ADAPTERS)
def tracker(request, tmp_path: Path) -> TrackerOps:
    match request.param:
        case "local":
            return ops("local", {}, repo=tmp_path)
        case "azure-devops":
            return ops("azure-devops", AZURE, FakeTransport(AzureBoard().answers))
        case "linear":
            return ops("linear", LINEAR, FakeTransport(LinearWorkspace().answers))
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


def _azure() -> tuple[TrackerOps, FakeTransport]:
    call = FakeTransport(AzureBoard().answers)
    return ops("azure-devops", AZURE, call), call


def test_azure_reparent_replaces_the_old_parent() -> None:
    azure, call = _azure()
    _, story = _story_under_feature(azure)
    other = azure.create_work_item(WorkItemKind.FEATURE, "G", "g", "").value
    azure.update_work_item(story.key, WorkItemChanges(parent=other.key))
    sent = [
        (a["action"], a.get("type") or a["updates"][0]["type"])
        for a in call.sent("wit_work_item_link_write")
    ]
    assert sent == [("unlink", "parent"), ("link", "parent")]
    assert call.sent("wit_work_item_link_write")[-1]["updates"][0]["linkToId"] == int(
        other.key
    )


def test_azure_reparent_without_a_parent_only_links() -> None:
    azure, call = _azure()
    story = azure.create_work_item(WorkItemKind.USER_STORY, "S", "s", "").value
    feature = azure.create_work_item(WorkItemKind.FEATURE, "F", "f", "").value
    azure.update_work_item(story.key, WorkItemChanges(parent=feature.key))
    assert [a["action"] for a in call.sent("wit_work_item_link_write")] == ["link"]


def test_azure_tags_are_written_joined() -> None:
    azure, call = _azure()
    story = azure.create_work_item(WorkItemKind.USER_STORY, "S", "s", "").value
    azure.update_work_item(story.key, WorkItemChanges(tags=("api", "ux")))
    assert {
        "op": "add",
        "path": "/fields/System.Tags",
        "value": "api; ux",
    } in call.sent("wit_work_item_write")[-1]["updates"]


def _linear() -> tuple[TrackerOps, FakeTransport]:
    call = FakeTransport(LinearWorkspace().answers)
    return ops("linear", LINEAR, call), call


def test_linear_tags_keep_the_kind_label() -> None:
    linear, call = _linear()
    _, story = _story_under_feature(linear)
    linear.update_work_item(story.key, WorkItemChanges(tags=("api",)))
    labels = call.sent("save_issue")[-1]["labels"]
    assert set(labels) >= {"api"} and len(labels) == 2
    assert linear.get_work_item(story.key).value.kind is WorkItemKind.USER_STORY
    assert linear.get_work_item(story.key).value.tags == ("api",)


def test_linear_empty_tags_keep_only_the_kind_label() -> None:
    linear, call = _linear()
    _, story = _story_under_feature(linear)
    linear.update_work_item(story.key, WorkItemChanges(tags=()))
    assert len(call.sent("save_issue")[-1]["labels"]) == 1
    assert linear.get_work_item(story.key).value.kind is WorkItemKind.USER_STORY
