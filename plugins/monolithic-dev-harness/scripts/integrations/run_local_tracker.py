from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
for _path in (_REPO_ROOT, _SCRIPTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from scripts.integrations.contracts import IntegrationError
from scripts.integrations.local_tracker import LOCAL_TRACKER_TOOLS, LocalTrackerStore

_PROTOCOL_VERSION = "2024-11-05"


def process_message(line: str, store: LocalTrackerStore) -> str:
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
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "local-tracker", "version": "1.0.0"},
            }
        elif method == "tools/list":
            response["result"] = {"tools": LOCAL_TRACKER_TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            result = handle_call(
                str(params.get("name")), params.get("arguments") or {}, store
            )
            response["result"] = {
                "content": [
                    {"type": "text", "text": json.dumps(result, default=_json_default)}
                ]
            }
        elif method == "notifications/initialized":
            return ""
        else:
            response["error"] = {
                "code": -32601,
                "message": f"Method not found: {method}",
            }
    except IntegrationError as exc:
        response["result"] = {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(exc.to_dict())}],
        }
    except Exception as exc:
        response["error"] = {"code": -32603, "message": str(exc)}
    return json.dumps(response)


def handle_call(name: str, args: dict[str, Any], store: LocalTrackerStore) -> Any:
    match name:
        case "get_work_item":
            return store.get_work_item(args["ref"])
        case "search_work_items":
            return store.search_work_items(args["query"], args.get("cursor"))
        case "create_work_item":
            return store.create_work_item(
                args["kind"],
                args["title"],
                args.get("description", ""),
                args.get("parentRef"),
            )
        case "list_children":
            return store.list_children(args["ref"])
        case "transition_work_item":
            return store.transition_work_item(args["ref"], args["state"])
        case "publish_artifact":
            return store.publish_artifact(
                args["ref"],
                args["kind"],
                args["title"],
                args["content"],
                args["revision"],
            )
        case "list_artifacts":
            return store.list_artifacts(args["ref"], args.get("kind"))
        case "link_development_artifact":
            return store.link_development_artifact(
                args["ref"], args["url"], args.get("type", "pull_request")
            )
    raise IntegrationError(
        "unsupported_capability", f"Unknown local tracker operation: {name}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local tracker MCP provider")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--root", default=".local-tracker")
    args = parser.parse_args(argv)
    store = LocalTrackerStore(
        {"projectRoot": str(args.project_root.resolve()), "root": args.root}
    )
    for line in sys.stdin:
        if line.strip():
            response = process_message(line, store)
            if response:
                print(response, flush=True)
    return 0


def _json_default(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        payload = dict(value.__dict__)
        for key, item in list(payload.items()):
            if hasattr(item, "value"):
                payload[key] = item.value
        return payload
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


if __name__ == "__main__":
    raise SystemExit(main())
