"""Stateful fakes of the remote trackers, answering in each provider's own reply shapes, so the
shared contract scenario (`test_tracker_contract.py`) runs the real adapters end to end."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

PARENT = "System.Parent"
ITERATION = "System.IterationPath"
TODAY = datetime.now(UTC).date()
START, FINISH = TODAY - timedelta(days=3), TODAY + timedelta(days=7)


class AzureBoard:
    """Azure DevOps work items as the `@azure-devops/mcp` tools read and write them."""

    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self.comments = {}
        self.next_id = 100
        self.answers = {
            "wit_work_item": self.read,
            "wit_work_item_write": self.write,
            "wit_work_item_comment_write": self.comment,
            "wit_work_item_link_write": self.link,
            "wit_query": self.query,
            "work": self.work,
        }
        self.sprint = {
            "id": "it-1",
            "name": "Sprint 1",
            "path": "proj\\Sprint 1",
            "attributes": {
                "startDate": f"{START.isoformat()}T00:00:00Z",
                "finishDate": f"{FINISH.isoformat()}T00:00:00Z",
                "timeFrame": 1,
            },
        }

    def work(self, args: dict[str, Any]) -> Any:
        preamble = f"Project: {args['project']}, Team: {args['team']}\n"
        match args["action"]:
            case "list_team_iterations":
                return preamble + json.dumps([self.sprint])
            case "get_team_capacity":
                return preamble + json.dumps({"teamMembers": []})
            case "get_team_settings":
                return preamble + json.dumps({"workingDays": ["monday", "friday"]})
        raise AssertionError(args)

    comments: dict[int, tuple[int, str]]

    def comment(self, args: dict[str, Any]) -> Any:
        match args["action"]:
            case "add":
                number = 900 + len(self.comments)
                self.comments[number] = (int(args["workItemId"]), args["text"])
                return {"id": number, "text": args["text"]}
            case "update":
                number = int(args["commentId"])
                self.comments[number] = (int(args["workItemId"]), args["text"])
                return {"id": number, "text": args["text"]}
        raise AssertionError(args)

    def record(self, number: int) -> dict[str, Any]:
        return {"id": number, "fields": dict(self.items[number])}

    def read(self, args: dict[str, Any]) -> Any:
        match args["action"]:
            case "get":
                return self.record(int(args["id"]))
            case "get_batch":
                return [
                    {"body": json.dumps(self.record(int(number)))}
                    for number in args["ids"]
                ]
            case "list_comments":
                return {
                    "comments": [
                        {"id": number, "text": text}
                        for number, (item, text) in self.comments.items()
                        if item == int(args["workItemId"])
                    ]
                }
            case "list_for_iteration":
                assert args["iterationId"] == self.sprint["id"], args
                return {
                    "workItemRelations": [
                        {"target": {"id": number}}
                        for number, fields in self.items.items()
                        if fields.get(ITERATION) == self.sprint["path"]
                    ]
                }
        raise AssertionError(args)

    def _new(self, kind: str, title: str, parent: int | None) -> dict[str, Any]:
        number = self.next_id
        self.next_id += 1
        self.items[number] = {
            "System.Id": number,
            "System.WorkItemType": kind,
            "System.State": "New",
            "System.Title": title,
            **({PARENT: parent} if parent else {}),
        }
        return {"id": number, "fields": {}}

    def write(self, args: dict[str, Any]) -> Any:
        match args["action"]:
            case "create":
                title = next(
                    f["value"] for f in args["fields"] if f["name"] == "System.Title"
                )
                return self._new(args["workItemType"], title, None)
            case "add_child":
                return [
                    self._new(
                        args["workItemType"], item["title"], int(args["parentId"])
                    )
                    for item in args["items"]
                ]
            case "update":
                fields = self.items[int(args["id"])]
                for op in args["updates"]:
                    if op["path"].startswith("/fields/"):
                        fields[op["path"].removeprefix("/fields/")] = op["value"]
                return self.record(int(args["id"]))
        raise AssertionError(args)

    def link(self, args: dict[str, Any]) -> Any:
        match args["action"]:
            case "link":
                for update in args["updates"]:
                    if update["type"] == "parent":
                        self.items[int(update["id"])][PARENT] = int(update["linkToId"])
                return {"linked": True}
            case "unlink":
                self.items[int(args["id"])].pop(PARENT, None)
                return {"unlinked": True}
        raise AssertionError(args)

    def query(self, args: dict[str, Any]) -> Any:
        found = re.search(r"\[System\.Parent\] = (\d+)", args["wiql"])
        numbers = (
            [n for n, f in self.items.items() if f.get(PARENT) == int(found.group(1))]
            if found
            else []
        )
        return {"workItems": [{"id": n} for n in numbers]}


class LinearWorkspace:
    """Linear issues as the hosted MCP server's issue tools read and write them."""

    def __init__(self) -> None:
        self.issues: dict[str, dict[str, Any]] = {}
        self.comments: dict[str, tuple[str, str]] = {}
        self.answers = {
            "get_issue": lambda args: self.issues[args["id"]],
            "list_issues": self.list,
            "save_issue": self.save,
            "list_comments": lambda args: [
                {"id": number, "body": body}
                for number, (issue, body) in self.comments.items()
                if issue == args["issueId"]
            ],
            "save_comment": self.comment,
            "list_cycles": lambda args: [self.cycle],
        }
        self.cycle = {
            "id": "cyc-1",
            "name": "Cycle 1",
            "number": 1,
            "startsAt": f"{START.isoformat()}T00:00:00Z",
            "endsAt": f"{FINISH.isoformat()}T00:00:00Z",
            "isActive": True,
        }

    def comment(self, args: dict[str, Any]) -> Any:
        if "id" in args:
            issue, _ = self.comments[args["id"]]
            self.comments[args["id"]] = (issue, args["body"])
            return {"id": args["id"], "body": args["body"]}
        number = f"c{len(self.comments) + 1}"
        self.comments[number] = (args["issueId"], args["body"])
        return {"id": number, "body": args["body"]}

    def save(self, args: dict[str, Any]) -> Any:
        if "id" not in args:
            identifier = f"ENG-{len(self.issues) + 1}"
            self.issues[identifier] = {
                "identifier": identifier,
                "state": "Backlog",
                "labels": [],
            }
            args = {**args, "id": identifier}
        issue = self.issues[args["id"]]
        for name, value in args.items():
            if name in (
                "title",
                "description",
                "labels",
                "parentId",
                "priority",
                "state",
                "cycle",
            ):
                issue[name] = list(value) if name == "labels" else value
        return issue

    def list(self, args: dict[str, Any]) -> Any:
        return [
            issue
            for issue in self.issues.values()
            if ("parentId" not in args or issue.get("parentId") == args["parentId"])
            and ("cycle" not in args or issue.get("cycle") == args["cycle"])
        ]
