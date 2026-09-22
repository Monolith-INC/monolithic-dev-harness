from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import scm_adapter, tracker_adapter
from .config import load_config, set_tracking_mode
from .contracts import IntegrationError

TOOLS = [
    {
        "name": "tracker_get_work_item",
        "description": "Retrieve one configured tracker work item.",
        "inputSchema": {
            "type": "object",
            "required": ["ref"],
            "properties": {"ref": {"type": "string"}},
        },
    },
    {
        "name": "tracker_search_work_items",
        "description": "Search configured tracker work items.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "cursor": {"type": "string"}},
        },
    },
    {
        "name": "tracker_create_work_item",
        "description": "Create a logical epic, feature, story, task, or bug.",
        "inputSchema": {
            "type": "object",
            "required": ["kind", "title"],
            "properties": {
                "kind": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "parentRef": {"type": "string"},
            },
        },
    },
    {
        "name": "tracker_list_children",
        "description": "List child work items.",
        "inputSchema": {
            "type": "object",
            "required": ["ref"],
            "properties": {"ref": {"type": "string"}},
        },
    },
    {
        "name": "tracker_transition_work_item",
        "description": "Transition a work item to a logical state.",
        "inputSchema": {
            "type": "object",
            "required": ["ref", "state"],
            "properties": {"ref": {"type": "string"}, "state": {"type": "string"}},
        },
    },
    {
        "name": "tracker_publish_artifact",
        "description": "Publish a versioned workflow artifact to a work item.",
        "inputSchema": {
            "type": "object",
            "required": ["ref", "kind", "title", "content", "revision"],
            "properties": {
                "ref": {"type": "string"},
                "kind": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "revision": {"type": "string"},
            },
        },
    },
    {
        "name": "tracker_list_artifacts",
        "description": "List workflow artifacts for a work item.",
        "inputSchema": {
            "type": "object",
            "required": ["ref"],
            "properties": {"ref": {"type": "string"}, "kind": {"type": "string"}},
        },
    },
    {
        "name": "tracker_link_development_artifact",
        "description": "Link a pull request or branch to a work item.",
        "inputSchema": {
            "type": "object",
            "required": ["ref", "url"],
            "properties": {
                "ref": {"type": "string"},
                "url": {"type": "string"},
                "type": {"type": "string"},
            },
        },
    },
    {
        "name": "scm_get_pull_request",
        "description": "Retrieve one configured pull request.",
        "inputSchema": {
            "type": "object",
            "required": ["ref"],
            "properties": {"ref": {"type": "string"}},
        },
    },
    {
        "name": "scm_create_pull_request",
        "description": "Create a pull request in the configured repository.",
        "inputSchema": {
            "type": "object",
            "required": ["title", "sourceBranch", "targetBranch"],
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "sourceBranch": {"type": "string"},
                "targetBranch": {"type": "string"},
            },
        },
    },
    {
        "name": "scm_list_review_threads",
        "description": "List active review threads.",
        "inputSchema": {
            "type": "object",
            "required": ["ref"],
            "properties": {"ref": {"type": "string"}},
        },
    },
    {
        "name": "scm_reply_to_thread",
        "description": "Reply to a review thread without changing its status.",
        "inputSchema": {
            "type": "object",
            "required": ["pullRequestRef", "threadRef", "content"],
            "properties": {
                "pullRequestRef": {"type": "string"},
                "threadRef": {"type": "string"},
                "content": {"type": "string"},
            },
        },
    },
    {
        "name": "scm_link_work_item",
        "description": "Link a work item to a pull request.",
        "inputSchema": {
            "type": "object",
            "required": ["pullRequestRef", "workItemRef"],
            "properties": {
                "pullRequestRef": {"type": "string"},
                "workItemRef": {"type": "string"},
            },
        },
    },
    {
        "name": "workflow_tracking_status",
        "description": "Report whether tracker workflows are enforced or paused.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "workflow_skip_tracker",
        "description": "Pause tracker-backed workflow enforcement without removing the configured provider.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "workflow_resume_tracker",
        "description": "Resume the configured tracker-backed workflow enforcement.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_call(
    name: str, args: dict[str, Any], *, project_root: Path | None = None
) -> Any:
    config = load_config(project_root)
    if name == "workflow_tracking_status":
        return _tracking_status(config)
    if name == "workflow_skip_tracker":
        return _tracking_status(set_tracking_mode(config.project_root, "skipped"))
    if name == "workflow_resume_tracker":
        return _tracking_status(set_tracking_mode(config.project_root, "enforced"))
    if name.startswith("tracker_"):
        if not config.tracking_enabled:
            raise IntegrationError(
                "tracking_paused",
                "Tracker operations are paused. Run /resume-tracker to restore the configured tracker.",
            )
        tracker = tracker_adapter(config.tracker)
        match name:
            case "tracker_get_work_item":
                return _serialize(tracker.get_work_item(args["ref"]))
            case "tracker_search_work_items":
                return tracker.search_work_items(args["query"], args.get("cursor"))
            case "tracker_create_work_item":
                return _serialize(
                    tracker.create_work_item(
                        args["kind"],
                        args["title"],
                        args.get("description", ""),
                        args.get("parentRef"),
                    )
                )
            case "tracker_list_children":
                return [_serialize(item) for item in tracker.list_children(args["ref"])]
            case "tracker_transition_work_item":
                return _serialize(
                    tracker.transition_work_item(args["ref"], args["state"])
                )
            case "tracker_publish_artifact":
                artifact = tracker.publish_artifact(
                    args["ref"],
                    args["kind"],
                    args["title"],
                    args["content"],
                    args["revision"],
                )
                payload = _serialize(artifact)
                outcome = artifact.outcome or "created"
                attempts = artifact.attempts if artifact.attempts is not None else 1
                payload["outcome"] = outcome
                payload["attempts"] = attempts
                _emit_telemetry(
                    {
                        "operation": "tracker_publish_artifact",
                        "adapter": config.tracker.get("adapter"),
                        "attempts": attempts,
                        "outcome": outcome,
                        "error_code": None,
                    }
                )
                return payload
            case "tracker_list_artifacts":
                return [
                    _serialize(item)
                    for item in tracker.list_artifacts(args["ref"], args.get("kind"))
                ]
            case "tracker_link_development_artifact":
                return tracker.link_development_artifact(
                    args["ref"], args["url"], args.get("type", "pull_request")
                )
    if name.startswith("scm_"):
        scm = scm_adapter(config.scm)
        match name:
            case "scm_get_pull_request":
                return _serialize(scm.get_pull_request(args["ref"]))
            case "scm_create_pull_request":
                return _serialize(
                    scm.create_pull_request(
                        args["title"],
                        args.get("description", ""),
                        args["sourceBranch"],
                        args["targetBranch"],
                    )
                )
            case "scm_list_review_threads":
                return [
                    _serialize(item) for item in scm.list_review_threads(args["ref"])
                ]
            case "scm_reply_to_thread":
                return scm.reply_to_thread(
                    args["pullRequestRef"], args["threadRef"], args["content"]
                )
            case "scm_link_work_item":
                return scm.link_work_item(args["pullRequestRef"], args["workItemRef"])
    raise IntegrationError(
        "unsupported_capability", f"Unknown integration operation: {name}"
    )


def process_message(line: str, *, project_root: Path | None = None) -> str:
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return ""
    if not isinstance(message, dict) or "id" not in message or "method" not in message:
        return ""
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
    try:
        method = message["method"]
        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "workflow-integrations", "version": "1.0.0"},
            }
        elif method == "tools/list":
            response["result"] = {"tools": _tools_for_project(project_root)}
        elif method == "tools/call":
            params = message.get("params") or {}
            try:
                result = handle_call(
                    str(params.get("name")),
                    params.get("arguments") or {},
                    project_root=project_root,
                )
                response["result"] = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, default=_json_default),
                        }
                    ]
                }
            except IntegrationError as exc:
                _emit_telemetry(
                    {
                        "operation": str((message.get("params") or {}).get("name")),
                        "adapter": None,
                        "attempts": 1,
                        "outcome": "error",
                        "error_code": exc.code,
                    }
                )
                response["result"] = {
                    "isError": True,
                    "content": [{"type": "text", "text": json.dumps(exc.to_dict())}],
                }
        elif method == "notifications/initialized":
            return ""
        else:
            response["error"] = {
                "code": -32601,
                "message": f"Method not found: {method}",
            }
    except Exception as exc:
        response["error"] = {"code": -32603, "message": str(exc)}
    return json.dumps(response)


def _serialize(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        payload = dict(value.__dict__)
        for key, item in list(payload.items()):
            if hasattr(item, "value"):
                payload[key] = item.value
        return payload
    return value


def _tracking_status(config: Any) -> dict[str, Any]:
    return {
        "mode": config.tracking_mode,
        "enabled": config.tracking_enabled,
        "adapter": config.tracker.get("adapter"),
    }


def _tools_for_project(project_root: Path | None) -> list[dict[str, Any]]:
    try:
        config = load_config(project_root)
    except IntegrationError:
        return TOOLS
    if config.tracking_enabled:
        return TOOLS
    return [tool for tool in TOOLS if not tool["name"].startswith("tracker_")]


def _emit_telemetry(payload: dict[str, Any]) -> None:
    import sys

    sys.stderr.write(json.dumps({"telemetry": payload}) + "\n")
    sys.stderr.flush()


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"not JSON serializable: {type(value).__name__}")
