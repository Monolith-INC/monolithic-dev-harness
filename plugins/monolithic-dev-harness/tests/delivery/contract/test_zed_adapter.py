"""Zed host adapter: parse/format round-trip, chat transport, and CLI dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from host_adapters import native_session_id, select_adapter
from host_adapters.interactions import chat_instruction, present
from host_adapters.zed_adapter import (
    format_zed_decision,
    parse_zed_payload,
    zed_session_id,
)
from policy.events import PolicyDecision

PLUGIN = Path(__file__).resolve().parents[3]


def _choice() -> dict:
    return {
        "id": "method",
        "header": "Review",
        "question": "Which method?",
        "options": [
            {"label": "Light", "description": "quick"},
            {"label": "Standard", "description": "balanced"},
        ],
    }


def test_select_adapter_resolves_zed() -> None:
    parse, format_decision = select_adapter("zed")
    assert parse is parse_zed_payload
    assert format_decision is format_zed_decision


def test_parse_zed_payload_builds_canonical_event() -> None:
    payload = {
        "tool_name": "edit_file",
        "tool_input": {"path": "lib/main.dart"},
        "cwd": "/repo",
    }
    event = parse_zed_payload(payload, project_root="/repo")
    assert event.client == "zed"
    # edit_file is a known edit tool, so the canonical event carries its kind.
    assert event.tool_name == "edit"
    assert event.kind == "edit"
    assert event.file_path == "lib/main.dart"
    assert event.workspace_root == "/repo"


def test_zed_session_id_is_empty_without_hook_payload() -> None:
    # Zed exposes no thread id to MCP servers; there is nothing to bind yet.
    assert zed_session_id({}) == ""
    assert native_session_id("zed", {}) == ""


def test_format_zed_decision_marks_deny() -> None:
    decision = PolicyDecision.deny("external write needs approval")
    out = format_zed_decision(decision)
    hook = out["hookSpecificOutput"]
    assert hook["hookEventName"] == "PreToolUse"
    assert hook["permissionDecision"] == "deny"
    assert hook["permissionDecisionReason"] == "external write needs approval"


def test_zed_present_uses_chat_transport() -> None:
    shown = present(_choice(), "zed", blocking_available=False)
    assert shown["host"] == "zed"
    assert shown["transport"] == "chat"
    assert "menu" in shown
    assert "1. **Light**" in shown["menu"]


def test_zed_chat_instruction_differs_from_default() -> None:
    zed = chat_instruction("zed")
    default = chat_instruction("text")
    assert "no native question control" in zed
    assert zed != default


def test_default_chat_instruction_unchanged_for_other_hosts() -> None:
    assert chat_instruction("text") == chat_instruction("claude")
    assert chat_instruction("cursor") == chat_instruction("codex")


def test_hosts_zed_capability_file_is_valid() -> None:
    data = json.loads((PLUGIN / "hosts" / "zed.json").read_text(encoding="utf-8"))
    assert data["host"] == "zed"
    assert data["product"]
    assert set(data["subagents"]) == {
        "start",
        "status",
        "follow_up",
        "cancel",
        "events",
    }
    assert all(not op["supported"] for op in data["subagents"].values())
    assert any("no hook" in note for note in data["notes"])


def test_zed_mcp_template_resolves_plugin_root() -> None:
    template = json.loads((PLUGIN / "zed.mcp.json").read_text(encoding="utf-8"))
    assert set(template) == {
        "backlog-orchestrator",
        "workflow-orchestrator",
        "workflow-integrations",
    }
    for entry in template.values():
        assert "${PLUGIN_ROOT}" in entry["args"][0]
        assert "env" in entry and "PYTHONPATH" in entry["env"]
