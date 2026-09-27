"""Each shipped adapter against its provider's reply shapes, through the one contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok
from integrations import artifacts
from integrations.contracts import ArtifactDraft, LogicalState, WorkItemKind

from .fakes import FakeTransport, module, ops

AZURE = {"organization": "o", "project": "proj"}


def ado_item(number, kind, state, parent=None):
    fields = {
        "System.Id": number,
        "System.Title": f"Item {number}",
        "System.WorkItemType": kind,
        "System.State": state,
    }
    return {
        "id": number,
        "fields": {**fields, **({"System.Parent": parent} if parent else {})},
    }


class AzureTest(unittest.TestCase):
    def setUp(self) -> None:
        def read(args):
            match args["action"]:
                case "get":
                    return ado_item(args["id"], "Feature", "New")
                case "get_batch":
                    return [
                        {
                            "body": json.dumps(
                                ado_item(i, "User Story", "Active", parent=1)
                            )
                        }
                        for i in args["ids"]
                    ]
                case "list_comments":
                    envelope = artifacts.encode(
                        ArtifactDraft("spec", "Spec", "body", "1")
                    )
                    return {
                        "comments": [
                            {"id": 9, "text": envelope},
                            {"id": 8, "text": "an ordinary comment"},
                        ]
                    }

        self.call = FakeTransport(
            {
                "wit_work_item": read,
                "wit_query": {"workItems": [{"id": 2}, {"id": 3}]},
                "wit_work_item_write": {"id": 10, "fields": {}},
                "wit_work_item_comment_write": {"id": 11},
                "wit_work_item_link_write": {"linked": True},
            }
        )
        self.tracker = ops("azure-devops", AZURE, self.call)

    def test_children_come_from_a_parent_query_and_a_batch_read(self) -> None:
        children = self.tracker.list_children("1").value
        self.assertEqual(
            [item.kind for item in children], [WorkItemKind.USER_STORY] * 2
        )
        self.assertEqual(
            (children[0].state, children[0].parent_id), (LogicalState.IN_PROGRESS, "1")
        )
        [query] = self.call.sent("wit_query")
        self.assertEqual((query["action"], query["project"]), ("wiql", "proj"))
        self.assertIn("[System.Parent] = 1", query["wiql"])

    def test_create_with_and_without_a_parent_then_read_back(self) -> None:
        created = self.tracker.create_work_item(
            WorkItemKind.FEATURE, "New", "body", ""
        ).value
        self.assertEqual(created.kind, WorkItemKind.FEATURE)
        first = self.call.sent("wit_work_item_write")[0]
        self.assertEqual(
            (first["action"], first["workItemType"]), ("create", "Feature")
        )
        self.assertNotIn("parentId", first)
        self.tracker.create_work_item(WorkItemKind.USER_STORY, "Story", "body", "10")
        last = self.call.sent("wit_work_item_write")[-1]
        self.assertEqual(
            (last["action"], last["parentId"], last["workItemType"]),
            ("add_child", 10, "User Story"),
        )

    def test_transition_writes_the_provider_state(self) -> None:
        self.tracker.transition_work_item("10", LogicalState.IN_PROGRESS)
        self.assertEqual(
            self.call.sent("wit_work_item_write")[-1]["updates"][0]["value"], "Active"
        )

    def test_only_enveloped_comments_are_artifacts(self) -> None:
        [artifact] = self.tracker.list_artifacts("10").value
        self.assertEqual(
            (artifact.id, artifact.kind, artifact.content), ("9", "spec", "body")
        )
        added = self.tracker.add_artifact(
            "10", ArtifactDraft("report", "R", "text", "2")
        ).value
        self.assertEqual((added.id, added.kind), ("11", "report"))
        self.assertTrue(
            self.call.sent("wit_work_item_comment_write")[0]["text"].startswith(
                artifacts.PREFIX
            )
        )

    def test_a_non_numeric_ref_fails_without_calling_the_server(self) -> None:
        self.assertEqual(
            self.tracker.get_work_item("ENG-1").failure.code, "invalid_request"
        )
        self.assertEqual(self.call.calls, [])

    def test_search_builds_wiql_from_text_conditions_or_statements(self) -> None:
        wiql = module("azure-devops").wiql
        self.assertIn(
            "[System.Title] CONTAINS 'foto d''estudante'", wiql("foto d'estudante")
        )
        self.assertIn(
            "AND ([System.WorkItemType] = 'Epic')",
            wiql("[System.WorkItemType] = 'Epic'"),
        )
        self.assertIn("AND ([Custom.Team] = 'A')", wiql("[Custom.Team] = 'A'"))
        self.assertIn("[System.Title] CONTAINS 'bug [urgent]'", wiql("bug [urgent]"))
        self.assertEqual(
            wiql("SELECT [System.Id] FROM WorkItems"),
            "SELECT [System.Id] FROM WorkItems",
        )
        page = self.tracker.search_work_items("x", "").value
        self.assertEqual((len(page.items), page.truncated), (2, False))

    def test_planning_reads_replies_and_names_hour_fields(self) -> None:
        tracker = ops("azure-devops", {**AZURE, "process": "Scrum"}, self.call)
        replies = {
            "iteration": {
                "value": [
                    {"name": "S0", "attributes": {"timeFrame": 0}},
                    {
                        "name": "S1",
                        "attributes": {"timeFrame": 1, "startDate": "2026-08-03"},
                    },
                ]
            },
            "work_items": {"value": [{"body": json.dumps(ado_item(5, "Task", "New"))}]},
        }
        reading = tracker.read_iteration(replies, "current").value
        self.assertEqual(str(reading.capacity.start_date), "2026-08-03")
        (item,) = tracker.iteration_items(replies, "current").value
        self.assertEqual(item.item_id, "5")
        self.assertEqual(
            dict(tracker.hour_fields(4.0, True)),
            {"/fields/Microsoft.VSTS.Scheduling.RemainingWork": 4.0},
        )

    def test_link_sends_a_hyperlink(self) -> None:
        self.assertEqual(
            self.tracker.link_development_artifact(
                "10", "https://x/pr/1", "pull_request"
            ).value,
            {"linked": True},
        )
        self.assertEqual(
            self.call.sent("wit_work_item_link_write")[0]["updates"][0]["type"],
            "hyperlink",
        )


class LinearTest(unittest.TestCase):
    def setUp(self) -> None:
        issue = lambda identifier, state="Todo", parent=None, labels=("Story",): {  # noqa: E731
            "id": "uuid-" + identifier,
            "identifier": identifier,
            "title": "T",
            "state": {"name": state},
            "labels": [{"name": label} for label in labels],
            **({"parent": {"identifier": parent}} if parent else {}),
        }
        self.issue = issue
        self.call = FakeTransport(
            {
                "get_issue": lambda args: issue(args["id"]),
                "save_issue": lambda args: issue(
                    args.get("id", "ENG-9"), args.get("state", "Backlog")
                ),
                "list_issues": lambda args: {
                    "issues": [
                        issue("ENG-2", parent="ENG-1"),
                        issue("ENG-3", parent="ENG-7"),
                    ],
                    "pageInfo": {"hasNextPage": True, "endCursor": "c2"},
                },
                "list_comments": {
                    "comments": [
                        {
                            "id": "c1",
                            "body": artifacts.encode(
                                ArtifactDraft("spec", "S", "b", "1")
                            ),
                        }
                    ]
                },
                "save_comment": {"comment": {"id": "c9"}},
            }
        )
        self.tracker = ops("linear", {"team": "ENG"}, self.call)

    def test_issues_map_to_work_items_by_identifier_label_and_state(self) -> None:
        item = self.tracker.get_work_item("eng-5").value
        self.assertEqual(
            (item.id, item.key, item.kind, item.state),
            ("ENG-5", "ENG-5", WorkItemKind.USER_STORY, LogicalState.READY),
        )
        self.assertEqual(self.call.sent("get_issue"), [{"id": "ENG-5"}])

    def test_create_sends_team_label_and_parent(self) -> None:
        self.tracker.create_work_item(WorkItemKind.TASK, "Do", "body", "eng-1")
        [sent] = self.call.sent("save_issue")
        self.assertEqual(
            (sent["team"], sent["labels"], sent["parentId"]), ("ENG", ["Task"], "ENG-1")
        )

    def test_transition_children_search_and_artifacts(self) -> None:
        moved = self.tracker.transition_work_item("ENG-4", LogicalState.DONE).value
        self.assertEqual(
            (self.call.sent("save_issue")[-1]["state"], moved.state),
            ("Done", LogicalState.DONE),
        )
        self.assertEqual(
            [item.key for item in self.tracker.list_children("ENG-1").value], ["ENG-2"]
        )
        self.assertEqual(
            self.tracker.search_work_items("x", "").value.next_cursor, "c2"
        )
        self.assertEqual(self.tracker.list_artifacts("ENG-1").value[0].kind, "spec")
        self.assertEqual(
            self.tracker.add_artifact(
                "ENG-1", ArtifactDraft("r", "R", "t", "1")
            ).value.id,
            "c9",
        )

    def test_a_reply_without_an_issue_is_a_provider_error(self) -> None:
        tracker = ops(
            "linear", {"team": "ENG"}, FakeTransport({"get_issue": {"nothing": True}})
        )
        self.assertEqual(tracker.get_work_item("ENG-1").failure.code, "provider_error")

    def test_planning_reads_cycle_dates_and_issue_estimates(self) -> None:
        replies = {
            "cycle": [
                {
                    "number": 7,
                    "startsAt": "2026-08-03T00:00:00Z",
                    "endsAt": "2026-08-14",
                }
            ],
            "issues": {
                "issues": [
                    {
                        **self.issue("ENG-2"),
                        "estimate": 3,
                        "assignee": {"name": "Ana"},
                        "cycle": {"number": 7},
                    },
                    {"title": "no identifier"},
                ]
            },
        }
        reading = self.tracker.read_iteration(replies, "current").value
        self.assertEqual(
            (str(reading.capacity.start_date), str(reading.capacity.finish_date)),
            ("2026-08-03", "2026-08-14"),
        )
        self.assertEqual(reading.capacity.members, ())
        self.assertIn("no team capacity", reading.warnings[0])
        (item,) = self.tracker.iteration_items(replies, "current").value
        self.assertEqual(
            (
                item.item_id,
                item.points,
                item.assigned_to,
                item.item_type,
                item.iteration,
            ),
            ("ENG-2", 3.0, "Ana", "user_story", "7"),
        )
        self.assertEqual(dict(self.tracker.hour_fields(4.0, True)), {})


class LocalTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.tracker = ops("local", {}, repo=self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_hierarchy_transitions_artifacts_and_links_persist(self) -> None:
        feature = self.tracker.create_work_item(
            WorkItemKind.FEATURE, "Feature", "", ""
        ).value
        story = self.tracker.create_work_item(
            WorkItemKind.USER_STORY, "Story", "about", feature.key
        ).value
        self.assertEqual(
            (feature.key, story.key, story.parent_id),
            ("FEATURE-0001", "STORY-0001", "FEATURE-0001"),
        )
        self.assertTrue(
            (self.repo / ".harness/tracker/backlog/STORY-0001.json").is_file()
        )
        refused = self.tracker.create_work_item(
            WorkItemKind.EPIC, "Epic", "", story.key
        )
        self.assertEqual(refused.failure.code, "invalid_hierarchy")
        moved = self.tracker.transition_work_item(
            "story-0001", LogicalState.IN_PROGRESS
        ).value
        self.assertEqual(moved.state, LogicalState.IN_PROGRESS)
        self.assertTrue(
            (self.repo / ".harness/tracker/in_progress/STORY-0001.json").is_file()
        )
        self.assertFalse(
            (self.repo / ".harness/tracker/backlog/STORY-0001.json").exists()
        )
        self.assertEqual(
            [item.key for item in self.tracker.list_children(feature.key).value],
            ["STORY-0001"],
        )
        self.tracker.add_artifact(
            story.key, ArtifactDraft("spec", "Tech spec", "text", "1")
        )
        [artifact] = self.tracker.list_artifacts(story.key).value
        self.assertEqual(
            (artifact.kind, artifact.title, artifact.content),
            ("spec", "Tech spec", "text"),
        )
        self.tracker.link_development_artifact(
            story.key, "https://x/pr/1", "pull_request"
        )
        linked = self.tracker.link_development_artifact(
            story.key, "https://x/pr/1", "pull_request"
        ).value
        self.assertTrue(linked["linked"])
        self.assertEqual(
            len(self.tracker.get_work_item(story.key).value.provider_data["links"]), 1
        )

    def test_planning_reads_the_capacity_file_and_sprint_items(self) -> None:
        folder = self.repo / ".harness/tracker/capacity"
        folder.mkdir(parents=True)
        (folder / "S1.json").write_text(
            json.dumps(
                {
                    "startDate": "2026-08-03",
                    "finishDate": "2026-08-14",
                    "members": [{"name": "Ana", "activities": [{"capacityPerDay": 6}]}],
                }
            )
        )
        story = self.tracker.create_work_item(
            WorkItemKind.USER_STORY, "S", "", ""
        ).value
        path = self.repo / ".harness/tracker/backlog" / f"{story.key}.json"
        record = json.loads(path.read_text())
        path.write_text(
            json.dumps({**record, "iteration": "S1", "points": 5, "remainingHours": 8})
        )
        reading = self.tracker.read_iteration({}, "S1").value
        self.assertEqual(reading.capacity.members[0].daily_hours, 6.0)
        (item,) = self.tracker.iteration_items({}, "S1").value
        self.assertEqual(
            (item.item_id, item.points, item.planned_hours), (story.key, 5.0, 8.0)
        )
        self.assertEqual(self.tracker.iteration_items({}, "S2").value, ())
        self.assertIn(
            "no capacity file", self.tracker.read_iteration({}, "S2").value.warnings[0]
        )
        self.assertEqual(
            dict(self.tracker.hour_fields(4.0, True)),
            {"remainingHours": 4.0, "estimatedHours": 4.0},
        )
        self.assertEqual(
            dict(self.tracker.hour_fields(4.0, False)), {"remainingHours": 4.0}
        )

    def test_search_pages_and_missing_items(self) -> None:
        tuple(
            self.tracker.create_work_item(WorkItemKind.TASK, f"Task {n}", "", "")
            for n in range(3)
        )
        self.assertEqual(len(self.tracker.search_work_items("task", "").value.items), 3)
        self.assertEqual(
            self.tracker.get_work_item("TASK-9999").failure.code, "work_item_not_found"
        )

    def test_a_corrupt_record_is_reported(self) -> None:
        folder = self.repo / ".harness/tracker/backlog"
        folder.mkdir(parents=True)
        (folder / "TASK-0001.json").write_text("{")
        self.assertIsInstance(self.tracker.get_work_item("TASK-0001"), Err)


class PublishTest(unittest.TestCase):
    """Publishing once per (title, revision), through any adapter's list and add operations."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tracker = ops("local", {}, repo=Path(self._tmp.name))
        self.key = self.tracker.create_work_item(
            WorkItemKind.TASK, "T", "", ""
        ).value.key
        self.draft = ArtifactDraft("spec", "Spec", "body", "1")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_the_second_publish_reuses_the_first(self) -> None:
        first = artifacts.publish(self.tracker, self.key, self.draft).value
        second = artifacts.publish(self.tracker, self.key, self.draft).value
        self.assertEqual(
            (first.outcome, second.outcome, second.attempts), ("created", "reused", 0)
        )

    def test_a_retryable_failure_looks_again_before_adding_again(self) -> None:
        from dataclasses import replace

        from core.result import err

        calls = []

        def flaky(ref, draft):
            calls.append(ref)
            return (
                err("provider_timeout", "slow", retryable=True)
                if len(calls) == 1
                else self.tracker.add_artifact(ref, draft)
            )

        published = artifacts.publish(
            replace(self.tracker, add_artifact=flaky),
            self.key,
            self.draft,
            pause=lambda _: None,
        ).value
        self.assertEqual(
            (published.outcome, published.attempts, len(calls)), ("created", 2, 2)
        )

    def test_a_non_retryable_failure_is_returned_after_one_attempt(self) -> None:
        from dataclasses import replace

        from core.result import err

        failing = replace(
            self.tracker, add_artifact=lambda ref, draft: err("provider_error", "no")
        )
        self.assertEqual(
            artifacts.publish(failing, self.key, self.draft).failure.code,
            "provider_error",
        )
        self.assertIsInstance(artifacts.publish(self.tracker, self.key, self.draft), Ok)
