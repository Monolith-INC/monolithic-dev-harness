"""The tracker base surface, the same scenario against every shipped adapter (Article 14).

Each adapter is built on its own provider's reply shapes (`trackers.py` holds the fakes for the
remote ones), so a scenario that passes here passes through the one neutral contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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
            _capacity(tmp_path, "S1", -3, 7)
            return ops("local", {}, repo=tmp_path)
        case "azure-devops":
            return ops("azure-devops", AZURE, FakeTransport(AzureBoard().answers))
        case "linear":
            return ops("linear", LINEAR, FakeTransport(LinearWorkspace().answers))
    raise AssertionError(request.param)


def _capacity(repo: Path, name: str, start: int, finish: int) -> None:
    today = datetime.now(UTC).date()
    (repo / f"capacity-{name}.json").write_text(
        json.dumps(
            {
                "startDate": (today + timedelta(days=start)).isoformat(),
                "finishDate": (today + timedelta(days=finish)).isoformat(),
            }
        )
    )


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


# --- sprints ------------------------------------------------------------------------------------


def test_current_sprint_has_its_dates(tracker: TrackerOps) -> None:
    sprint = tracker.current_sprint().value
    assert sprint.start <= datetime.now(UTC).date() <= sprint.end
    assert sprint.path


def test_sprint_items_are_the_sprints_items(tracker: TrackerOps) -> None:
    _, story = _story_under_feature(tracker)
    _, outside = _story_under_feature(tracker)
    sprint = tracker.current_sprint().value
    tracker.update_work_item(story.key, WorkItemChanges(iteration=sprint.path))
    # A tracker may place new items in the current sprint; this one is moved out of it.
    tracker.update_work_item(outside.key, WorkItemChanges(iteration="Elsewhere"))
    listed = {item.item_id for item in tracker.sprint_items("current").value}
    assert story.id in listed and outside.id not in listed


def test_sprint_capacity_reads_the_current_sprint(tracker: TrackerOps) -> None:
    sprint = tracker.current_sprint().value
    reading = tracker.sprint_capacity("current").value
    assert reading.capacity.start_date == sprint.start


def test_no_local_sprint_covering_today_names_the_files(tmp_path: Path) -> None:
    _capacity(tmp_path, "OLD", -30, -20)
    failed = ops("local", {}, repo=tmp_path).current_sprint()
    assert isinstance(failed, Err) and failed.failure.code == "no_current_sprint"
    assert "capacity-OLD.json" in failed.failure.message


def test_overlapping_local_sprints_take_the_latest_start(tmp_path: Path) -> None:
    _capacity(tmp_path, "LONG", -20, 10)
    _capacity(tmp_path, "NEW", -2, 10)
    assert ops("local", {}, repo=tmp_path).current_sprint().value.name == "NEW"


def test_azure_sprint_items_list_then_batch() -> None:
    azure, call = _azure()
    story = azure.create_work_item(WorkItemKind.USER_STORY, "S", "s", "").value
    sprint = azure.current_sprint().value
    azure.update_work_item(story.key, WorkItemChanges(iteration=sprint.path))
    azure.sprint_items("current")
    reads = [a["action"] for a in call.sent("wit_work_item")]
    assert reads[-2:] == ["list_for_iteration", "get_batch"]
    assert call.sent("wit_work_item")[-2]["iterationId"] == sprint.id
