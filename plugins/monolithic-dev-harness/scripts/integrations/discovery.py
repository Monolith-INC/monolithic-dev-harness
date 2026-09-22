"""Provider capability discovery and logical mapping presets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .contracts import IntegrationError
from .mcp_client import StdioMcpClient, client_from_connection

REQUIRED_TRACKER_OPS = (
    "get_work_item",
    "search_work_items",
    "create_work_item",
    "list_children",
    "transition_work_item",
    "publish_artifact",
    "list_artifacts",
    "link_development_artifact",
)

REQUIRED_SCM_OPS = (
    "get_pull_request",
    "create_pull_request",
    "list_review_threads",
    "reply_to_thread",
    "link_work_item",
)

REQUIRED_KIND_KEYS = ("epic", "feature", "user_story", "task", "bug")
REQUIRED_STATE_KEYS = ("backlog", "ready", "in_progress", "done", "canceled")

LINEAR_KIND_PRESET = {
    "epic": "Epic",
    "feature": "Feature",
    "user_story": "Story",
    "task": "Task",
    "bug": "Bug",
}
LINEAR_STATE_PRESET = {
    "backlog": "Backlog",
    "ready": "Todo",
    "in_progress": "In Progress",
    "done": "Done",
    "canceled": "Canceled",
}

ADO_KIND_PRESET = {
    "epic": "Epic",
    "feature": "Feature",
    "user_story": "User Story",
    "task": "Task",
    "bug": "Bug",
}
ADO_STATE_PRESET = {
    "backlog": "New",
    "ready": "Approved",
    "in_progress": "Active",
    "done": "Closed",
    "canceled": "Removed",
}

LOCAL_KIND_PRESET = {kind: kind for kind in REQUIRED_KIND_KEYS}
LOCAL_STATE_PRESET = {state: state for state in REQUIRED_STATE_KEYS}

TRACKER_BINDING_CANDIDATES: dict[str, tuple[str, ...]] = {
    "get_work_item": ("get_issue", "get_work_item", "wit_get_work_item"),
    "search_work_items": (
        "list_issues",
        "search_issues",
        "search_work_items",
        "wit_query_by_wiql",
    ),
    "create_work_item": (
        "save_issue",
        "create_issue",
        "create_work_item",
        "wit_create_work_item",
    ),
    "list_children": (
        "list_issue_children",
        "list_children",
        "list_issues",
        "wit_get_work_items",
    ),
    "transition_work_item": (
        "save_issue",
        "update_issue",
        "transition_issue",
        "transition_work_item",
        "wit_update_work_item",
    ),
    "publish_artifact": (
        "save_comment",
        "create_comment",
        "publish_artifact",
        "wit_add_work_item_comment",
    ),
    "list_artifacts": ("list_comments", "list_artifacts", "wit_get_work_item_comments"),
    "link_development_artifact": (
        "save_comment",
        "create_comment",
        "link_development_artifact",
        "wit_add_artifact_link",
    ),
}

SCM_BINDING_CANDIDATES: dict[str, tuple[str, ...]] = {
    "get_pull_request": (
        "repo_get_pull_request_by_id",
        "get_pull_request",
        "get_pull_request_by_id",
    ),
    "create_pull_request": ("repo_create_pull_request", "create_pull_request"),
    "list_review_threads": (
        "repo_list_pull_request_threads",
        "list_review_threads",
        "list_pull_request_threads",
    ),
    "reply_to_thread": ("repo_reply_to_comment", "reply_to_thread", "reply_to_comment"),
    "link_work_item": (
        "wit_link_work_item_to_pull_request",
        "link_work_item",
        "link_work_item_to_pull_request",
    ),
}


@dataclass(frozen=True)
class DiscoveryResult:
    discovered_tools: tuple[str, ...]
    resolved_bindings: dict[str, str]
    suggested_mappings: dict[str, dict[str, str]]
    missing_capabilities: tuple[str, ...]
    provider: str
    kind: str


def mapping_presets(adapter: str) -> dict[str, dict[str, str]]:
    match adapter:
        case "linear":
            return {
                "kinds": dict(LINEAR_KIND_PRESET),
                "states": dict(LINEAR_STATE_PRESET),
            }
        case "azure_devops":
            return {"kinds": dict(ADO_KIND_PRESET), "states": dict(ADO_STATE_PRESET)}
        case "local_tracker":
            return {
                "kinds": dict(LOCAL_KIND_PRESET),
                "states": dict(LOCAL_STATE_PRESET),
            }
        case _:
            return {"kinds": {}, "states": {}}


def resolve_bindings(
    discovered: Mapping[str, Any] | list[str] | tuple[str, ...],
    candidates: Mapping[str, tuple[str, ...]],
    preferred: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], tuple[str, ...]]:
    names = _tool_names(discovered)
    resolved: dict[str, str] = {}
    missing: list[str] = []
    preferred = preferred or {}
    for operation, aliases in candidates.items():
        ordered = (
            (preferred[operation],)
            + tuple(a for a in aliases if a != preferred[operation])
            if preferred.get(operation)
            else aliases
        )
        match = next((alias for alias in ordered if alias in names), None)
        if match is None:
            missing.append(operation)
        else:
            resolved[operation] = match
    return resolved, tuple(missing)


def discover_provider_capabilities(
    *,
    kind: str,
    adapter: str,
    connection: dict[str, Any],
    preferred_bindings: Mapping[str, str] | None = None,
    discovered_tools: Mapping[str, Any] | list[str] | None = None,
    client: StdioMcpClient | None = None,
) -> DiscoveryResult:
    if adapter == "github":
        return DiscoveryResult(
            discovered_tools=("github",),
            resolved_bindings={},
            suggested_mappings={"kinds": {}, "states": {}},
            missing_capabilities=(),
            provider="github",
            kind="github",
        )
    tools = discovered_tools
    if tools is None:
        mcp = client or client_from_connection(connection)
        tools = mcp.list_tools()

    candidates = (
        TRACKER_BINDING_CANDIDATES if kind == "tracker" else SCM_BINDING_CANDIDATES
    )
    resolved, missing = resolve_bindings(tools, candidates, preferred_bindings)
    mappings = (
        mapping_presets(adapter) if kind == "tracker" else {"kinds": {}, "states": {}}
    )
    return DiscoveryResult(
        discovered_tools=tuple(_tool_names(tools)),
        resolved_bindings=resolved,
        suggested_mappings=mappings,
        missing_capabilities=missing,
        provider=adapter,
        kind=kind,
    )


def validate_tracker_mappings(mappings: Mapping[str, Any]) -> tuple[str, ...]:
    kinds = mappings.get("kinds") if isinstance(mappings.get("kinds"), dict) else {}
    states = mappings.get("states") if isinstance(mappings.get("states"), dict) else {}
    missing: list[str] = []
    for key in REQUIRED_KIND_KEYS:
        if not str(kinds.get(key) or "").strip():
            missing.append(f"kinds.{key}")
    for key in REQUIRED_STATE_KEYS:
        if not str(states.get(key) or "").strip():
            missing.append(f"states.{key}")
    return tuple(missing)


def validate_bindings(bindings: Mapping[str, Any], *, kind: str) -> tuple[str, ...]:
    required = REQUIRED_TRACKER_OPS if kind == "tracker" else REQUIRED_SCM_OPS
    if kind == "github":
        return ()
    return tuple(op for op in required if not str(bindings.get(op) or "").strip())


def apply_discovery_to_config(
    config: dict[str, Any],
    *,
    tracker_discovery: DiscoveryResult | None = None,
    scm_discovery: DiscoveryResult | None = None,
) -> dict[str, Any]:
    result = dict(config)
    if tracker_discovery is not None:
        tracker = dict(result.get("tracker") or {})
        tracker["bindings"] = dict(tracker_discovery.resolved_bindings)
        tracker["mappings"] = {
            "kinds": dict(tracker_discovery.suggested_mappings.get("kinds") or {}),
            "states": dict(tracker_discovery.suggested_mappings.get("states") or {}),
        }
        result["tracker"] = tracker
    if scm_discovery is not None and scm_discovery.kind != "github":
        scm = dict(result.get("scm") or {})
        scm["bindings"] = dict(scm_discovery.resolved_bindings)
        result["scm"] = scm
    return result


def verify_integration_capabilities(
    config: dict[str, Any], *, probe: bool = False
) -> list[str]:
    problems: list[str] = []
    tracker = config.get("tracker") if isinstance(config.get("tracker"), dict) else {}
    scm = config.get("scm") if isinstance(config.get("scm"), dict) else {}
    problems.extend(
        f"tracker missing binding: {op}"
        for op in validate_bindings(tracker.get("bindings") or {}, kind="tracker")
    )
    problems.extend(
        f"tracker mapping missing: {key}"
        for key in validate_tracker_mappings(tracker.get("mappings") or {})
    )
    scm_adapter = str(scm.get("adapter") or "")
    if scm_adapter not in {"", "github"}:
        problems.extend(
            f"scm missing binding: {op}"
            for op in validate_bindings(scm.get("bindings") or {}, kind="scm")
        )
    if not probe:
        return problems
    try:
        if tracker.get("connection"):
            names = set(client_from_connection(tracker["connection"]).list_tools())
            for op, tool in (tracker.get("bindings") or {}).items():
                if tool and tool not in names:
                    problems.append(
                        f"tracker binding {op} -> {tool} not advertised by provider"
                    )
        if scm_adapter not in {"", "github"} and scm.get("connection"):
            names = set(client_from_connection(scm["connection"]).list_tools())
            for op, tool in (scm.get("bindings") or {}).items():
                if tool and tool not in names:
                    problems.append(
                        f"scm binding {op} -> {tool} not advertised by provider"
                    )
    except IntegrationError as exc:
        problems.append(f"provider probe failed: {exc.code}: {exc}")
    return problems


def _tool_names(
    discovered: Mapping[str, Any] | list[str] | tuple[str, ...] | None,
) -> set[str]:
    if discovered is None:
        return set()
    if isinstance(discovered, (list, tuple)):
        names: set[str] = set()
        for item in discovered:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
        return names
    if isinstance(discovered, dict):
        tools = discovered.get("tools")
        if isinstance(tools, list):
            return _tool_names(tools)
        return {str(key) for key in discovered}
    return set()
