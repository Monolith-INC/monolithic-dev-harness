import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.integrations.adapters import (
    AzureDevOpsTrackerAdapter,
    AzureReposScmAdapter,
    GitHubScmAdapter,
    LinearTrackerAdapter,
)
from scripts.integrations.contracts import (
    ArtifactRef,
    IntegrationError,
    LogicalState,
    WorkItemKind,
)
from scripts.integrations.local_tracker import (
    LOCAL_TRACKER_BINDINGS,
    LocalTrackerAdapter,
)
from scripts.integrations.publish import publish_artifact_idempotent


class FakeClient:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((tool, arguments))
        value = self.responses.get(tool)
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return value(arguments)
        return value


def _linear_config(client: FakeClient) -> dict[str, Any]:
    adapter = LinearTrackerAdapter(
        {
            "adapter": "linear",
            "connection": {"command": "true", "args": []},
            "bindings": {
                "get_work_item": "get_issue",
                "search_work_items": "list_issues",
                "create_work_item": "create_issue",
                "list_children": "list_issues",
                "transition_work_item": "update_issue",
                "publish_artifact": "create_comment",
                "list_artifacts": "list_comments",
                "link_development_artifact": "create_comment",
            },
            "mappings": {
                "kinds": {
                    "feature": "Feature",
                    "user_story": "Story",
                    "task": "Task",
                    "bug": "Bug",
                    "epic": "Epic",
                },
                "states": {
                    "backlog": "Backlog",
                    "ready": "Todo",
                    "in_progress": "In Progress",
                    "done": "Done",
                    "canceled": "Canceled",
                },
            },
        }
    )
    adapter.client = client
    return adapter


class AdapterContractTests(unittest.TestCase):
    def test_local_tracker_persists_hierarchy_transitions_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = LocalTrackerAdapter(
                {
                    "adapter": "local_tracker",
                    "connection": {
                        "command": sys.executable,
                        "args": [
                            str(
                                Path(__file__).parents[3]
                                / "scripts"
                                / "integrations"
                                / "run_local_tracker.py"
                            ),
                            "--project-root",
                            str(root),
                            "--root",
                            ".local-tracker",
                        ],
                    },
                    "bindings": dict(LOCAL_TRACKER_BINDINGS),
                    "root": ".local-tracker",
                    "mappings": {
                        "kinds": {
                            "epic": "epic",
                            "feature": "feature",
                            "user_story": "user_story",
                            "task": "task",
                            "bug": "bug",
                        },
                        "states": {
                            "backlog": "backlog",
                            "ready": "ready",
                            "in_progress": "in_progress",
                            "done": "done",
                            "canceled": "canceled",
                        },
                    },
                }
            )
            epic = adapter.create_work_item("epic", "Quality gates", "Outcome")
            feature = adapter.create_work_item(
                "feature", "Local tracker", "Scope", epic.key
            )
            story = adapter.create_work_item(
                "user_story", "Use local records", "Story", feature.key
            )
            task = adapter.create_work_item(
                "task", "Persist records", "Task", story.key
            )

            self.assertEqual(epic.key, "EPIC-0001")
            self.assertEqual(
                [item.key for item in adapter.list_children(epic.key)], [feature.key]
            )
            with self.assertRaises(IntegrationError) as raised:
                adapter.create_work_item("task", "Invalid child", "", feature.key)
            self.assertEqual(raised.exception.code, "invalid_hierarchy")

            moved = adapter.transition_work_item(task.key, "in_progress")
            self.assertEqual(moved.state, LogicalState.IN_PROGRESS)
            self.assertTrue(
                (root / ".local-tracker" / "in_progress" / f"{task.key}.json").is_file()
            )
            artifact = adapter.publish_artifact(
                task.key, "spec", "Implementation plan", "# Plan", "1"
            )
            self.assertEqual(artifact.outcome, "created")
            self.assertEqual(
                adapter.publish_artifact(
                    task.key, "spec", "Implementation plan", "# Plan", "1"
                ).outcome,
                "reused",
            )
            link = adapter.link_development_artifact(
                task.key, "https://example.test/pr/1"
            )
            self.assertTrue(link["linked"])
            self.assertEqual(len(adapter.list_artifacts(task.key)), 1)

    def test_linear_get_transition_children_and_publish(self):
        client = FakeClient(
            {
                "get_issue": {
                    "id": "ENG-1",
                    "identifier": "ENG-1",
                    "title": "Feature",
                    "kind": "Feature",
                    "state": "In Progress",
                },
                "update_issue": {
                    "id": "ENG-1",
                    "identifier": "ENG-1",
                    "title": "Feature",
                    "kind": "Feature",
                    "state": "Done",
                },
                "list_issues": {
                    "items": [
                        {
                            "id": "ENG-2",
                            "identifier": "ENG-2",
                            "title": "Story",
                            "kind": "Story",
                            "state": "Todo",
                            "parentId": "ENG-1",
                        },
                        {
                            "id": "ENG-9",
                            "identifier": "ENG-9",
                            "title": "Other",
                            "kind": "Story",
                            "state": "Todo",
                            "parentId": "ENG-8",
                        },
                    ]
                },
                "list_comments": {"items": []},
                "create_comment": {
                    "id": "c1",
                    "kind": "spec",
                    "title": "Spec",
                    "revision": "1",
                },
            }
        )
        adapter = _linear_config(client)
        item = adapter.get_work_item("ENG-1")
        self.assertEqual(item.kind, WorkItemKind.FEATURE)
        self.assertEqual(item.state, LogicalState.IN_PROGRESS)
        done = adapter.transition_work_item("ENG-1", "done")
        self.assertEqual(done.state, LogicalState.DONE)
        children = adapter.list_children("ENG-1")
        self.assertEqual([child.key for child in children], ["ENG-2"])
        created = adapter.publish_artifact("ENG-1", "spec", "Spec", "body", "1")
        self.assertEqual(created.outcome, "created")
        client.responses["list_comments"] = {
            "items": [{"id": "c1", "kind": "spec", "title": "Spec", "revision": "1"}]
        }
        reused = adapter.publish_artifact("ENG-1", "spec", "Spec", "body", "1")
        self.assertEqual(reused.outcome, "reused")

    def test_azure_devops_list_children(self):
        client = FakeClient(
            {
                "wit_get_work_items": {
                    "items": [
                        {
                            "id": 2,
                            "title": "Story",
                            "type": "User Story",
                            "state": "Approved",
                            "parentId": 1,
                        },
                    ]
                }
            }
        )
        adapter = AzureDevOpsTrackerAdapter(
            {
                "adapter": "azure_devops",
                "connection": {"command": "true", "args": []},
                "bindings": {"list_children": "wit_get_work_items"},
                "mappings": {
                    "kinds": {
                        "user_story": "User Story",
                        "feature": "Feature",
                        "task": "Task",
                        "bug": "Bug",
                        "epic": "Epic",
                    },
                    "states": {
                        "ready": "Approved",
                        "backlog": "New",
                        "in_progress": "Active",
                        "done": "Closed",
                        "canceled": "Removed",
                    },
                },
            }
        )
        adapter.client = client
        children = adapter.list_children("1")
        self.assertEqual(children[0].kind, WorkItemKind.USER_STORY)

    def test_azure_repos_pr_ops(self):
        client = FakeClient(
            {
                "repo_get_pull_request_by_id": {
                    "id": 7,
                    "number": 7,
                    "title": "PR",
                    "url": "https://example/pr/7",
                    "sourceBranch": "feature/1",
                    "targetBranch": "main",
                    "state": "active",
                },
                "repo_create_pull_request": {
                    "id": 8,
                    "number": 8,
                    "title": "New",
                    "url": "https://example/pr/8",
                    "source": "feature/2",
                    "target": "main",
                    "state": "active",
                },
                "repo_list_pull_request_threads": {
                    "items": [{"id": "t1", "comment": "nit", "status": "active"}]
                },
                "repo_reply_to_comment": {"ok": True},
                "wit_link_work_item_to_pull_request": {"linked": True},
            }
        )
        adapter = AzureReposScmAdapter(
            {
                "adapter": "azure_repos",
                "repository": "repo",
                "project": "proj",
                "connection": {"command": "true", "args": []},
                "bindings": {
                    "get_pull_request": "repo_get_pull_request_by_id",
                    "create_pull_request": "repo_create_pull_request",
                    "list_review_threads": "repo_list_pull_request_threads",
                    "reply_to_thread": "repo_reply_to_comment",
                    "link_work_item": "wit_link_work_item_to_pull_request",
                },
            }
        )
        adapter.client = client
        pr = adapter.get_pull_request("7")
        self.assertEqual(pr.number, "7")
        created = adapter.create_pull_request("New", "body", "feature/2", "main")
        self.assertEqual(created.number, "8")
        threads = adapter.list_review_threads("7")
        self.assertEqual(threads[0].id, "t1")
        self.assertEqual(adapter.reply_to_thread("7", "t1", "ack")["ok"], True)
        self.assertEqual(adapter.link_work_item("7", "42")["linked"], True)

    def test_github_adapter_uses_injected_runner(self):
        adapter = GitHubScmAdapter(
            {
                "adapter": "github",
                "owner": "o",
                "repo": "r",
                "connection": {"command": "true", "args": []},
                "bindings": {},
            }
        )

        def fake_run(args: list[str]) -> Any:
            if args[:2] == ["pr", "view"]:
                return {
                    "number": 3,
                    "title": "Hello",
                    "url": "https://example/3",
                    "headRefName": "feature/x",
                    "baseRefName": "main",
                    "state": "OPEN",
                }
            return []

        adapter._run = fake_run  # type: ignore[method-assign]
        pr = adapter.get_pull_request("3")
        self.assertEqual(pr.title, "Hello")
        self.assertEqual(pr.source_branch, "feature/x")
        self.assertEqual(pr.target_branch, "main")

    def test_github_link_work_item_persists_body_marker(self):
        adapter = GitHubScmAdapter(
            {
                "adapter": "github",
                "owner": "o",
                "repo": "r",
                "connection": {"command": "true", "args": []},
                "bindings": {},
            }
        )
        edits: list[list[str]] = []

        def fake_run(args: list[str]) -> Any:
            if args[:2] == ["pr", "view"]:
                return {"body": "Existing body"}
            return {}

        def fake_run_text(args: list[str]) -> str:
            edits.append(args)
            return ""

        adapter._run = fake_run  # type: ignore[method-assign]
        adapter._run_text = fake_run_text  # type: ignore[method-assign]
        result = adapter.link_work_item("3", "CW-1")
        self.assertTrue(result["linked"])
        self.assertEqual(edits[0][:2], ["pr", "edit"])
        self.assertIn("Work item: CW-1", edits[0][edits[0].index("--body") + 1])

    def test_comment_body_envelope_round_trip(self):
        from scripts.integrations.adapters import _artifact, _encode_artifact_envelope

        body = _encode_artifact_envelope(
            kind="tech_spec", title="Spec", revision="3", content="# Body"
        )
        artifact = _artifact({"id": "c1", "body": body})
        self.assertEqual(artifact.kind, "tech_spec")
        self.assertEqual(artifact.title, "Spec")
        self.assertEqual(artifact.revision, "3")
        self.assertIn("# Body", str(artifact.provider_data.get("content")))

    def test_linear_create_maps_kind(self):
        calls = []

        class FakeClient:
            def call(self, tool, arguments):
                calls.append((tool, arguments))
                return {
                    "id": "1",
                    "identifier": "ABC-1",
                    "title": arguments["title"],
                    "kind": arguments["kind"],
                    "state": "Backlog",
                }

        adapter = LinearTrackerAdapter(
            {
                "adapter": "linear",
                "connection": {"command": "true", "args": []},
                "bindings": {"create_work_item": "create_issue"},
                "mappings": {"kinds": {"feature": "Feature"}, "states": {}},
            }
        )
        adapter.client = FakeClient()
        item = adapter.create_work_item("feature", "Title", "desc")
        self.assertEqual(calls[0][1]["kind"], "Feature")
        self.assertEqual(item.key, "ABC-1")


class PublishHelperTests(unittest.TestCase):
    def test_reused_skips_create(self):
        calls = {"create": 0}

        def list_fn() -> list[ArtifactRef]:
            return [ArtifactRef("1", "spec", "Spec", "1")]

        def create_fn() -> ArtifactRef:
            calls["create"] += 1
            return ArtifactRef("2", "spec", "Spec", "1")

        result = publish_artifact_idempotent(
            list_fn=list_fn, create_fn=create_fn, title="Spec", revision="1"
        )
        self.assertEqual(result["outcome"], "reused")
        self.assertEqual(calls["create"], 0)

    def test_retryable_then_success(self):
        attempts = {"n": 0}

        def list_fn() -> list[ArtifactRef]:
            return []

        def create_fn() -> ArtifactRef:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise IntegrationError("provider_timeout", "slow", retryable=True)
            return ArtifactRef("2", "spec", "Spec", "1")

        result = publish_artifact_idempotent(
            list_fn=list_fn,
            create_fn=create_fn,
            title="Spec",
            revision="1",
            sleep_fn=lambda _: None,
        )
        self.assertEqual(result["outcome"], "created")
        self.assertEqual(result["attempts"], 2)

    def test_non_retryable_fails_once(self):
        attempts = {"n": 0}

        def list_fn() -> list[ArtifactRef]:
            return []

        def create_fn() -> ArtifactRef:
            attempts["n"] += 1
            raise IntegrationError("provider_error", "boom", retryable=False)

        with self.assertRaises(IntegrationError):
            publish_artifact_idempotent(
                list_fn=list_fn,
                create_fn=create_fn,
                title="Spec",
                revision="1",
                sleep_fn=lambda _: None,
            )
        self.assertEqual(attempts["n"], 1)

    def test_retryable_timeout_reliists_before_duplicate(self):
        attempts = {"n": 0}
        listed = {"n": 0}
        created = ArtifactRef("2", "spec", "Spec", "1")

        def list_fn():
            listed["n"] += 1
            if attempts["n"] >= 1:
                return [created]
            return []

        def create_fn():
            attempts["n"] += 1
            raise IntegrationError("provider_timeout", "slow", retryable=True)

        result = publish_artifact_idempotent(
            list_fn=list_fn,
            create_fn=create_fn,
            title="Spec",
            revision="1",
            sleep_fn=lambda _s: None,
        )
        self.assertEqual(result["outcome"], "reused")
        self.assertGreaterEqual(listed["n"], 2)


if __name__ == "__main__":
    unittest.main()
