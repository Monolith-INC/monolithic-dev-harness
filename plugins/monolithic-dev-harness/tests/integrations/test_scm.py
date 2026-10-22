from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import MappingProxyType

from core.result import Err, Ok
from harness.settings import Selection
from integrations import scm
from integrations.contracts import PullRequestDraft

from .fakes import FakeTransport

PULL_REQUEST = {
    "pullRequestId": 7,
    "title": "PR",
    "sourceRefName": "refs/heads/feature/1",
    "targetRefName": "refs/heads/develop",
    "status": "active",
    "repository": {
        "id": "repo-guid",
        "webUrl": "https://dev.azure.com/o/p/_git/repo",
        "project": {"id": "project-guid"},
    },
}


class AzureReposTest(unittest.TestCase):
    def setUp(self) -> None:
        self.call = FakeTransport(
            {
                "repo_pull_request": lambda args: {
                    **PULL_REQUEST,
                    "pullRequestId": args["pullRequestId"],
                },
                # `create` returns a trimmed shape: the repository is a name and there is no URL.
                "repo_pull_request_write": {
                    "pullRequestId": 8,
                    "status": 1,
                    "repository": "repo",
                },
                "repo_pull_request_thread": [
                    {
                        "id": 5,
                        "status": "active",
                        "threadContext": {
                            "filePath": "/a.dart",
                            "rightFileStart": {"line": 3},
                        },
                        "comments": [
                            {"content": "nit", "author": {"displayName": "Ana"}}
                        ],
                    }
                ],
                "repo_pull_request_thread_write": {"id": 1},
                "wit_work_item_link_write": {"linked": True},
            }
        )
        self.ops = scm.azure_repos(
            {"organization": "o", "project": "proj", "repository": "repo"}, self.call
        )

    def test_pull_requests_threads_replies_and_links(self) -> None:
        pull_request = self.ops.get_pull_request("7").value
        self.assertEqual(
            (pull_request.number, pull_request.source_branch), ("7", "feature/1")
        )
        self.assertEqual(
            pull_request.url, "https://dev.azure.com/o/p/_git/repo/pullrequest/7"
        )
        created = self.ops.create_pull_request(
            PullRequestDraft("New", "body", "feature/2", "develop")
        ).value
        self.assertEqual(created.number, "8")
        self.assertTrue(created.url.endswith("/_git/repo/pullrequest/8"))
        [create] = self.call.sent("repo_pull_request_write")
        self.assertEqual(
            (create["action"], create["isDraft"], create["sourceRefName"]),
            ("create", True, "refs/heads/feature/2"),
        )
        [thread] = self.ops.list_review_threads("7").value
        self.assertEqual(
            (thread.id, thread.reviewer, thread.line, thread.file),
            ("5", "Ana", 3, "/a.dart"),
        )
        self.ops.reply_to_thread("7", "5", "ack")
        self.assertEqual(
            self.call.sent("repo_pull_request_thread_write")[0]["threadId"], 5
        )
        self.assertEqual(self.ops.link_work_item("7", "42").value, {"linked": True})
        [link] = self.call.sent("wit_work_item_link_write")
        self.assertEqual(
            (link["repositoryId"], link["projectId"], link["workItemId"]),
            ("repo-guid", "project-guid", 42),
        )

    def test_review_threads_are_opened_edited_and_given_a_status(self) -> None:
        self.assertEqual(
            self.ops.create_review_thread("7", "/a.dart", 3, 5, 41, "Name this.").value,
            {"id": 1},
        )
        self.ops.update_thread_comment("7", "5", "Reworded.")
        self.ops.set_thread_status("7", "5", "Fixed")
        created, updated, closed = self.call.sent("repo_pull_request_thread_write")
        self.assertEqual(
            created,
            {
                "action": "create",
                "project": "proj",
                "repositoryId": "repo",
                "pullRequestId": 7,
                "filePath": "/a.dart",
                "rightFileStartLine": 3,
                "rightFileStartOffset": 1,
                "rightFileEndLine": 5,
                "rightFileEndOffset": 41,
                "content": "Name this.",
            },
        )
        self.assertEqual(
            (
                updated["action"],
                updated["pullRequestId"],
                updated["threadId"],
                updated["commentId"],
                updated["content"],
            ),
            ("update", 7, 5, 1, "Reworded."),
        )
        self.assertEqual(
            (
                closed["action"],
                closed["pullRequestId"],
                closed["threadId"],
                closed["status"],
            ),
            ("update_status", 7, 5, "Fixed"),
        )

    def test_a_reference_that_is_not_a_number_is_refused_before_any_call(self) -> None:
        for result in (
            self.ops.create_review_thread("PR-7", "/a.dart", 1, 1, 9, "x"),
            self.ops.update_thread_comment("7", "first", "x"),
            self.ops.set_thread_status("PR-7", "5", "Fixed"),
        ):
            self.assertIsInstance(result, Err)
        self.assertEqual(self.call.sent("repo_pull_request_thread_write"), [])


class GitHubTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ran: list[tuple[str, ...]] = []
        self.body = "Summary"

        def run(args: tuple[str, ...]):
            self.ran.append(args)
            match args[:2]:
                case ("pr", "view") if "body" in args:
                    return Ok(json.dumps({"body": self.body}))
                case ("pr", "view"):
                    return Ok(
                        json.dumps(
                            {
                                "number": 12,
                                "title": "T",
                                "url": "https://github.com/o/r/pull/12",
                                "headRefName": "f",
                                "baseRefName": "develop",
                                "state": "OPEN",
                            }
                        )
                    )
                case ("pr", "create"):
                    return Ok("https://github.com/o/r/pull/12\n")
                case ("pr", "edit"):
                    self.body = args[args.index("--body") + 1]
                    return Ok("")
                case _:
                    return Ok(
                        json.dumps(
                            [
                                {
                                    "id": 3,
                                    "path": "a.py",
                                    "line": 4,
                                    "user": {"login": "bo"},
                                    "body": "hm",
                                }
                            ]
                        )
                    )

        self.ops = scm.github({"owner": "o", "repo": "r"}, run)

    def test_create_opens_a_draft_and_reads_it_back(self) -> None:
        created = self.ops.create_pull_request(
            PullRequestDraft("T", "b", "f", "develop")
        ).value
        self.assertEqual(created.number, "12")
        self.assertIn("--draft", self.ran[0])
        self.assertEqual(self.ran[1][:3], ("pr", "view", "12"))

    def test_threads_and_the_work_item_marker_is_written_once(self) -> None:
        [thread] = self.ops.list_review_threads("12").value
        self.assertEqual((thread.file, thread.line, thread.reviewer), ("a.py", 4, "bo"))
        self.ops.link_work_item("12", "ENG-1")
        self.ops.link_work_item("12", "ENG-1")
        self.assertEqual(self.body.count("Work item: ENG-1"), 1)
        self.assertEqual(sum(1 for args in self.ran if args[:2] == ("pr", "edit")), 1)

    def test_hosts_without_review_thread_writes_refuse_them(self) -> None:
        for ops in (self.ops, scm.local()):
            for refused in (
                ops.create_review_thread("12", "a.py", 1, 1, 9, "x"),
                ops.update_thread_comment("12", "3", "x"),
                ops.set_thread_status("12", "3", "Fixed"),
            ):
                self.assertEqual(refused.failure.code, "unsupported_capability")
                self.assertIn("code host", refused.failure.message)
        self.assertEqual(self.ran, [])


class BuildTest(unittest.TestCase):
    def test_missing_values_are_reported(self) -> None:
        built = scm.build(
            Selection("github", "shipped", MappingProxyType({"owner": "o"})), Path(".")
        )
        self.assertIn("repo", built.failure.message)
