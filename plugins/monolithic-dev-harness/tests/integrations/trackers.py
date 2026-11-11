"""Stateful fakes of the remote trackers, answering in each provider's own reply shapes, so the
shared contract scenario (`test_tracker_contract.py`) runs the real adapters end to end."""

from __future__ import annotations

import json
import re
from typing import Any

PARENT = "System.Parent"


class AzureBoard:
    """Azure DevOps work items as the `@azure-devops/mcp` tools read and write them."""

    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self.next_id = 100
        self.answers = {
            "wit_work_item": self.read,
            "wit_work_item_write": self.write,
            "wit_work_item_link_write": self.link,
            "wit_query": self.query,
        }

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
                return {"comments": []}
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
        self.answers = {
            "get_issue": lambda args: self.issues[args["id"]],
            "list_issues": self.list,
            "save_issue": self.save,
            "list_comments": lambda args: [],
        }

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
            ):
                issue[name] = list(value) if name == "labels" else value
        return issue

    def list(self, args: dict[str, Any]) -> Any:
        return [
            issue
            for issue in self.issues.values()
            if "parentId" not in args or issue.get("parentId") == args["parentId"]
        ]
