"""Each shipped adapter against its provider's reply shapes, through the one contract."""

from __future__ import annotations

import html
import json
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok
from integrations import artifacts
from integrations.contracts import (
    ArtifactDraft,
    Hours,
    LogicalState,
    TrackerOps,
    WorkItemChanges,
    WorkItemKind,
)

from .fakes import FakeTransport, ops

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
        [child] = [
            write
            for write in self.call.sent("wit_work_item_write")
            if write["action"] == "add_child"
        ]
        self.assertEqual((child["parentId"], child["workItemType"]), (10, "User Story"))

    def test_a_task_gets_its_storys_sprint_and_assignee(self) -> None:
        story = ado_item(20, "User Story", "Active")
        story["fields"]["System.IterationPath"] = "proj\\Sprint 65"
        story["fields"]["System.AssignedTo"] = {"uniqueName": "ana@example.com"}
        call = FakeTransport(
            {
                "wit_work_item": lambda args: (
                    story
                    if args["id"] == 20
                    else ado_item(args["id"], "Task", "New", parent=20)
                ),
                "wit_work_item_write": {"id": 30, "fields": {}},
            }
        )
        ops("azure-devops", AZURE, call).create_work_item(
            WorkItemKind.TASK, "Do it", "body", "20"
        )
        update = call.sent("wit_work_item_write")[-1]
        self.assertEqual((update["action"], update["id"]), ("update", 30))
        self.assertEqual(
            {u["path"]: u["value"] for u in update["updates"]},
            {
                "/fields/System.AssignedTo": "ana@example.com",
                "/fields/System.IterationPath": "proj\\Sprint 65",
            },
        )

    def created_story(
        self, fields: dict, work: object = None, highest: float | None = 2000.0
    ) -> FakeTransport:
        """Create a Story on a fake Azure whose new item carries `fields`."""
        story = ado_item(40, "User Story", "New")
        story["fields"].update(fields)
        ranked = {"id": 5, "fields": {"Microsoft.VSTS.Common.StackRank": highest}}

        def read(args):
            match args["action"]:
                case "get":
                    return story
                case "get_batch":
                    return [{"body": json.dumps(ranked)}]

        call = FakeTransport(
            {
                "wit_work_item": read,
                "wit_query": {"workItems": [{"id": 5}] if highest else []},
                "wit_work_item_write": {"id": 40, "fields": {}},
                **({"work": work} if work is not None else {}),
            }
        )
        ops("azure-devops", AZURE, call).create_work_item(
            WorkItemKind.USER_STORY, "Story", "body", ""
        )
        return call

    def test_a_new_story_goes_to_its_creator_and_the_current_sprint(self) -> None:
        sprint = [{"path": "proj\\Sprint 66", "attributes": {"timeFrame": 1}}]
        call = self.created_story(
            {"System.CreatedBy": {"uniqueName": "ana@example.com"}},
            work=f"Project: proj, Team: proj Team\n{json.dumps(sprint)}",
        )
        [asked] = call.sent("work")
        self.assertEqual(
            (asked["action"], asked["project"], asked["team"], asked["timeframe"]),
            ("list_team_iterations", "proj", "proj Team", "current"),
        )
        placed = call.sent("wit_work_item_write")[1]
        self.assertEqual(
            {u["path"]: u["value"] for u in placed["updates"]},
            {
                "/fields/System.AssignedTo": "ana@example.com",
                "/fields/System.IterationPath": "proj\\Sprint 66",
            },
        )

    def test_an_unreadable_sprint_leaves_the_sprint_and_still_creates(self) -> None:
        call = self.created_story(
            {"System.CreatedBy": {"uniqueName": "ana@example.com"}}
        )
        placed = call.sent("wit_work_item_write")[1]
        self.assertEqual(
            {u["path"]: u["value"] for u in placed["updates"]},
            {"/fields/System.AssignedTo": "ana@example.com"},
        )

    def test_a_new_backlog_item_is_ranked_after_the_last_one(self) -> None:
        rank = self.created_story({}).sent("wit_work_item_write")[-1]
        self.assertEqual(
            rank["updates"],
            [
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.StackRank",
                    "value": 3000.0,
                }
            ],
        )

    def test_the_first_ranked_item_takes_the_first_rank_step(self) -> None:
        rank = self.created_story({}, highest=None).sent("wit_work_item_write")[-1]
        self.assertEqual(rank["updates"][0]["value"], 1000.0)

    def test_an_item_that_has_a_rank_keeps_it(self) -> None:
        writes = self.created_story({"Microsoft.VSTS.Common.StackRank": 10.0}).sent(
            "wit_work_item_write"
        )
        self.assertEqual([write["action"] for write in writes], ["create"])

    def test_an_update_never_reranks(self) -> None:
        self.tracker.update_work_item("10", WorkItemChanges(title="Renamed"))
        self.assertFalse(
            any(
                u["path"].endswith("StackRank")
                for write in self.call.sent("wit_work_item_write")
                for u in write.get("updates", ())
            )
        )

    def test_transition_writes_the_provider_state(self) -> None:
        self.tracker.transition_work_item("10", LogicalState.IN_PROGRESS)
        self.assertEqual(
            self.call.sent("wit_work_item_write")[-1]["updates"][0]["value"], "Active"
        )

    def test_update_writes_only_the_named_fields_then_reads_back(self) -> None:
        updated = self.tracker.update_work_item(
            "10",
            WorkItemChanges(
                title="Refined",
                description="body",
                story_points=3,
                hours=Hours(5),
                assignee="ana@example.com",
                iteration="proj\\Sprint 2",
            ),
        ).value
        [sent] = self.call.sent("wit_work_item_write")
        self.assertEqual((sent["action"], sent["id"]), ("update", 10))
        self.assertEqual(
            {
                update["path"]: update["value"]
                for update in sent["updates"]
                if not update["path"].startswith("/multilineFieldsFormat/")
            },
            {
                "/fields/System.Title": "Refined",
                "/fields/System.Description": "body",
                "/fields/Microsoft.VSTS.Scheduling.StoryPoints": 3,
                "/fields/Microsoft.VSTS.Scheduling.RemainingWork": 5,
                "/fields/System.AssignedTo": "ana@example.com",
                "/fields/System.IterationPath": "proj\\Sprint 2",
            },
        )
        # The MCP server's `update` takes plain JSON-Patch ops; Markdown is a field of its own.
        self.assertIn(
            {
                "op": "add",
                "path": "/multilineFieldsFormat/System.Description",
                "value": "Markdown",
            },
            sent["updates"],
        )
        self.assertTrue(all(set(u) == {"op", "path", "value"} for u in sent["updates"]))
        self.assertEqual(updated.key, "10")
        self.tracker.update_work_item("10", WorkItemChanges(title="Only"))
        self.assertEqual(
            [u["path"] for u in self.call.sent("wit_work_item_write")[-1]["updates"]],
            ["/fields/System.Title"],
        )

    def test_an_update_that_changes_nothing_is_refused(self) -> None:
        self.assertIsInstance(
            self.tracker.update_work_item("10", WorkItemChanges()), Err
        )
        self.assertEqual(self.call.sent("wit_work_item_write"), [])

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
        def sent(query: str) -> str:
            self.tracker.search_work_items(query, "")
            return self.call.sent("wit_query")[-1]["wiql"]

        self.assertIn(
            "[System.Title] CONTAINS 'foto d''estudante'", sent("foto d'estudante")
        )
        self.assertIn(
            "AND ([System.WorkItemType] = 'Epic')",
            sent("[System.WorkItemType] = 'Epic'"),
        )
        self.assertIn("AND ([Custom.Team] = 'A')", sent("[Custom.Team] = 'A'"))
        self.assertIn("[System.Title] CONTAINS 'bug [urgent]'", sent("bug [urgent]"))
        self.assertEqual(
            sent("SELECT [System.Id] FROM WorkItems"),
            "SELECT [System.Id] FROM WorkItems",
        )
        page = self.tracker.search_work_items("x", "").value
        self.assertEqual((len(page.items), page.truncated), (2, False))

    def sprint_server(self, batch: object) -> FakeTransport:
        """A fake Azure DevOps server for the sprint reads: two sprints, S1 current, whose
        iteration lists item 5; `batch` is what the batch read of its fields answers."""
        iterations = {
            "value": [
                {"id": "s0", "name": "S0", "attributes": {"timeFrame": 0}},
                {
                    "id": "s1",
                    "name": "S1",
                    "attributes": {"timeFrame": 1, "startDate": "2026-08-03"},
                },
            ]
        }

        def work(args):
            return {
                "list_team_iterations": iterations,
                "get_team_capacity": [],
                "get_team_settings": {},
            }[args["action"]]

        def read(args):
            match args["action"]:
                case "list_for_iteration":
                    return {"workItemRelations": [{"target": {"id": 5}}]}
                case "get_batch":
                    return batch

        return FakeTransport({"work": work, "wit_work_item": read})

    def test_planning_reads_the_sprint_and_names_hour_fields(self) -> None:
        tracker = ops(
            "azure-devops",
            {**AZURE, "process": "Scrum"},
            self.sprint_server(
                {"value": [{"body": json.dumps(ado_item(5, "Task", "New"))}]}
            ),
        )
        reading = tracker.sprint_capacity("current").value
        self.assertEqual(str(reading.capacity.start_date), "2026-08-03")
        (item,) = tracker.sprint_items("current").value
        self.assertEqual(item.item_id, "5")
        self.assertTrue(tracker.records_hours)

    def test_hours_write_remaining_work_and_the_first_estimate_where_the_process_has_it(
        self,
    ) -> None:
        def hour_paths(process: str, hours: Hours) -> set[str]:
            ops(
                "azure-devops", {**AZURE, "process": process}, self.call
            ).update_work_item("10", WorkItemChanges(hours=hours))
            return {
                u["path"] for u in self.call.sent("wit_work_item_write")[-1]["updates"]
            }

        remaining = "/fields/Microsoft.VSTS.Scheduling.RemainingWork"
        original = "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate"
        self.assertEqual(hour_paths("agile", Hours(4, True)), {remaining, original})
        self.assertEqual(hour_paths("cmmi", Hours(4, True)), {remaining, original})
        self.assertEqual(hour_paths("agile", Hours(4)), {remaining})
        self.assertEqual(hour_paths("agile", Hours(0, True)), {remaining})
        # Scrum has no Original Estimate, and an unstated process does not risk writing it.
        self.assertEqual(hour_paths("scrum", Hours(4, True)), {remaining})
        self.assertEqual(hour_paths("", Hours(4, True)), {remaining})

    def test_a_work_items_reply_of_ids_alone_is_refused_not_read_as_empty(self) -> None:
        """A batch read that answers with ids only would count as no work and overstate
        everyone's free hours, so it is refused."""
        relations = {"workItemRelations": [{"rel": None, "target": {"id": 5}}]}
        for reply in (relations, relations["workItemRelations"]):
            refused = ops(
                "azure-devops", AZURE, self.sprint_server(reply)
            ).sprint_items("current")
            self.assertEqual(refused.failure.code, "ids_only")
            self.assertIn("only work item ids", refused.failure.message)

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

    def test_update_saves_the_named_fields_and_refuses_hours(self) -> None:
        self.tracker.update_work_item(
            "eng-4",
            WorkItemChanges(
                title="Refined",
                description="body",
                story_points=3,
                assignee="ana",
                iteration="Cycle 2",
            ),
        )
        self.assertEqual(
            self.call.sent("save_issue")[-1],
            {
                "id": "ENG-4",
                "title": "Refined",
                "description": "body",
                "estimate": 3,
                "assignee": "ana",
                "cycle": "Cycle 2",
            },
        )
        refused = self.tracker.update_work_item(
            "ENG-4", WorkItemChanges(hours=Hours(2))
        )
        self.assertIn("no hours", refused.failure.message)

    def test_a_reply_without_an_issue_is_a_provider_error(self) -> None:
        tracker = ops(
            "linear", {"team": "ENG"}, FakeTransport({"get_issue": {"nothing": True}})
        )
        self.assertEqual(tracker.get_work_item("ENG-1").failure.code, "provider_error")

    def cycles(self, replies: dict) -> TrackerOps:
        """The Linear adapter on a fake server answering the cycle reads with `replies`."""
        return ops(
            "linear",
            {"team": "ENG"},
            FakeTransport(
                {
                    "list_cycles": lambda args: replies.get(
                        "cycle",
                        [
                            {
                                "id": "c7",
                                "number": 7,
                                "isActive": True,
                                "startsAt": "2026-08-03",
                            }
                        ],
                    ),
                    "list_issues": lambda args: replies.get("issues", []),
                }
            ),
        )

    def test_planning_reads_cycle_dates_and_issue_estimates(self) -> None:
        replies = {
            "cycle": [
                {"number": 6, "startsAt": "2026-07-20", "endsAt": "2026-07-31"},
                {
                    "number": 7,
                    "isActive": True,
                    "startsAt": "2026-08-03T00:00:00Z",
                    "endsAt": "2026-08-14",
                },
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
        tracker = self.cycles(replies)
        reading = tracker.sprint_capacity("current").value
        self.assertEqual(
            (str(reading.capacity.start_date), str(reading.capacity.finish_date)),
            ("2026-08-03", "2026-08-14"),
        )
        self.assertEqual(reading.capacity.members, ())
        self.assertIn("no team capacity", reading.warnings[0])
        (item,) = tracker.sprint_items("current").value
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
        self.assertFalse(tracker.records_hours)
        named = tracker.sprint_capacity("6").value.capacity
        self.assertEqual(str(named.start_date), "2026-07-20")
        missing = tracker.sprint_capacity("99").value
        self.assertIsNone(missing.capacity.start_date)
        self.assertIn("'99'", missing.warnings[-1])

    def test_planning_tolerates_odd_assignee_and_estimate_shapes(self) -> None:
        replies = {
            "issues": [
                {
                    **self.issue("ENG-3"),
                    "assignee": {"id": "u1"},
                    "estimate": {"value": 2},
                },
                {**self.issue("ENG-4"), "assignee": "Bia", "estimate": "x"},
            ]
        }
        first, second = self.cycles(replies).sprint_items("current").value
        self.assertEqual((first.assigned_to, first.points), (None, 2.0))
        self.assertEqual((second.assigned_to, second.points), ("Bia", None))


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
            ("FEATURE-0001", "STORY-0002", "FEATURE-0001"),
        )
        self.assertTrue((self.repo / "Tickets/Ready/0002-story.md").is_file())
        refused = self.tracker.create_work_item(
            WorkItemKind.EPIC, "Epic", "", story.key
        )
        self.assertEqual(refused.failure.code, "invalid_hierarchy")
        moved = self.tracker.transition_work_item(
            "story-0002", LogicalState.IN_PROGRESS
        ).value
        self.assertEqual(moved.state, LogicalState.IN_PROGRESS)
        self.assertTrue((self.repo / "Tickets/InProgress/0002-story.md").is_file())
        self.assertFalse((self.repo / "Tickets/Ready/0002-story.md").exists())
        self.assertEqual(
            [item.key for item in self.tracker.list_children(feature.key).value],
            ["STORY-0002"],
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
        (self.repo / "capacity-S1.json").write_text(
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
        self.tracker.update_work_item(
            story.key,
            WorkItemChanges(story_points=5, iteration="S1", hours=Hours(8, False)),
        )
        # A draft is not an item, even when it names the sprint.
        (self.repo / "Tickets/Ready/task-stray.md").write_text(
            "---\ntype: ticket\nwork_item_type: Task\niteration: S1\n---\n\nStray\n"
        )
        reading = self.tracker.sprint_capacity("S1").value
        self.assertEqual(reading.capacity.members[0].daily_hours, 6.0)
        (item,) = self.tracker.sprint_items("S1").value
        self.assertEqual(
            (item.item_id, item.points, item.planned_hours), (story.key, 5.0, 8.0)
        )
        self.assertEqual(self.tracker.sprint_items("S2").value, ())
        # A sprint with no capacity file cannot be checked, so it is refused, not read as empty.
        missing = self.tracker.sprint_capacity("S2").failure
        self.assertEqual(missing.code, "no_capacity")
        self.assertIn("capacity-S2.json", missing.message)
        self.assertTrue(self.tracker.records_hours)

    def test_no_sprint_name_is_the_current_sprint_never_a_made_up_one(self) -> None:
        """No sprint name means the current sprint: with none covering today, nothing is read
        as a sprint and no unplanned item is counted."""
        (self.repo / "capacity-OLD.json").write_text(
            json.dumps({"startDate": "2020-01-06", "finishDate": "2020-01-17"})
        )
        for ref in ("", "  "):
            self.assertEqual(
                self.tracker.sprint_capacity(ref).failure.code, "no_current_sprint"
            )
            self.assertEqual(
                self.tracker.sprint_items(ref).failure.code, "no_current_sprint"
            )

    def test_update_changes_the_record_and_reads_it_back(self) -> None:
        story = self.tracker.create_work_item(
            WorkItemKind.USER_STORY, "Draft", "draft text", ""
        ).value
        task = self.tracker.create_work_item(
            WorkItemKind.TASK, "Step", "", story.key
        ).value
        updated = self.tracker.update_work_item(
            story.key,
            WorkItemChanges(
                title="Refined",
                description="refined text",
                story_points=3,
                assignee="ana",
                iteration="Sprint 2",
            ),
        ).value
        self.assertEqual(
            (updated.title, updated.description), ("Refined", "refined text")
        )
        stored = self.tracker.get_work_item(story.key).value.provider_data
        self.assertEqual(
            (stored["story_points"], stored["assigned_to"], stored["iteration"]),
            (3, "ana", "Sprint 2"),
        )
        self.tracker.update_work_item(task.key, WorkItemChanges(hours=Hours(4, True)))
        hours = self.tracker.get_work_item(task.key).value.provider_data
        self.assertEqual((hours["remaining_hours"], hours["effort_hours"]), (4, 4))
        self.assertIsInstance(
            self.tracker.update_work_item("STORY-0042", WorkItemChanges(title="x")), Err
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
        folder = self.repo / "Tickets/Ready"
        folder.mkdir(parents=True)
        (folder / "0001-x.md").write_text(
            '---\nprovider_id: "TASK-0001"\nwork_item_type: Chore\n---\n\nx\n'
        )
        self.assertIsInstance(self.tracker.get_work_item("TASK-0001"), Err)

    def test_an_item_is_a_ticket_file_in_the_toolkit_format(self) -> None:
        """Front matter as `references/ticket-structure.md` gives it; the description is the body."""
        epic = self.tracker.create_work_item(WorkItemKind.EPIC, "Épico: um", "", "")
        feature = self.tracker.create_work_item(
            WorkItemKind.FEATURE,
            "Reset notice",
            "## 🎯 Objective\n\nSay so.",
            "EPIC-0001",
        ).value
        text = (self.repo / "Tickets/Ready/0002-reset-notice.md").read_text()
        self.assertTrue(text.startswith("---\n"))
        for line in (
            'title: "Reset notice"',
            "type: ticket",
            "work_item_type: Feature",
            "provider: local",
            'provider_id: "FEATURE-0002"',
            'parent_id: "EPIC-0001"',
        ):
            self.assertIn(line + "\n", text)
        self.assertTrue(text.endswith("---\n\n## 🎯 Objective\n\nSay so.\n"))
        self.assertEqual(feature.description, "## 🎯 Objective\n\nSay so.")
        self.assertTrue((self.repo / "Tickets/Ready/0001-epico-um.md").is_file())
        self.assertEqual(epic.value.title, "Épico: um")

    def test_creating_an_item_replaces_its_draft(self) -> None:
        """The toolkit renames a draft with the provider id once the item exists."""
        drafts = self.repo / "Tickets/Ready"
        drafts.mkdir(parents=True)
        (drafts / "draft-reset-notice.md").write_text(
            "---\ntype: ticket\nwork_item_type: User Story\nstory_points: 2\n"
            "language: en\ntags: [ticket, user-story]\nstatus: draft\n---\n\nThe body.\n"
        )
        (drafts / "draft-other.md").write_text(
            "---\ntype: ticket\nwork_item_type: User Story\n---\n\nAnother.\n"
        )
        story = self.tracker.create_work_item(
            WorkItemKind.USER_STORY, "Reset notice", "The body.", ""
        ).value
        self.assertEqual(
            sorted(path.name for path in drafts.iterdir()),
            ["0001-reset-notice.md", "draft-other.md"],
        )
        self.assertEqual(story.key, "STORY-0001")
        # The draft's front matter stays with the item; `status` never does.
        kept = self.tracker.get_work_item(story.key).value.provider_data
        self.assertEqual(
            (kept["story_points"], kept["language"], kept["tags"]),
            (2, "en", ["ticket", "user-story"]),
        )
        self.assertNotIn("status", kept)


class EnvelopeTest(unittest.TestCase):
    def test_a_comment_the_tracker_stored_html_escaped_is_still_an_artifact(
        self,
    ) -> None:
        draft = ArtifactDraft("spec", "Spec", 'body with "quotes" & <tags>', "1")
        stored = html.escape(artifacts.encode(draft))
        self.assertIn("&quot;kind&quot;", stored)
        self.assertEqual(artifacts.decode(stored), Ok(draft))

    def test_an_ordinary_comment_is_not_an_artifact(self) -> None:
        self.assertEqual(
            artifacts.decode("&quot;thanks&quot;").failure.code, "not_an_artifact"
        )


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
