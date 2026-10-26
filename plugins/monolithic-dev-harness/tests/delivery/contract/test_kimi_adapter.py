"""Kimi host adapter: parse/format round-trip and capability declaration."""

from __future__ import annotations

import json
from pathlib import Path

from harness.rules import Decision
from host_adapters import hook_bridge, native_session_id, select_adapter
from host_adapters.kimi_adapter import (
    format_kimi_decision,
    kimi_session_id,
    parse_kimi_payload,
)
from policy.events import PolicyDecision

PLUGIN = Path(__file__).resolve().parents[3]


def test_select_adapter_resolves_kimi() -> None:
    parse, format_decision = select_adapter("kimi")
    assert parse is parse_kimi_payload
    assert format_decision is format_kimi_decision


def test_parse_kimi_payload_builds_canonical_event() -> None:
    # Shape per the official hooks doc: session_id/cwd/hook_event_name/tool_name/tool_input.
    payload = {
        "session_id": "k-1",
        "cwd": "/repo",
        "hook_event_name": "PreToolUse",
        "tool_name": "edit_file",
        "tool_input": {"path": "lib/main.dart"},
        "tool_call_id": "call-9",
    }
    event = parse_kimi_payload(payload, project_root="/repo")
    assert event.client == "kimi"
    assert event.host_session_id == "k-1"
    # edit_file is a known edit tool, so the canonical event carries its kind.
    assert event.tool_name == "edit"
    assert event.kind == "edit"
    assert event.file_path == "lib/main.dart"
    assert event.workspace_root == "/repo"


def test_kimi_session_id_comes_from_the_payload() -> None:
    assert kimi_session_id({"session_id": " k-123 "}) == "k-123"
    assert kimi_session_id({}) == ""
    assert native_session_id("kimi", {"session_id": "k-9"}) == "k-9"


def test_format_kimi_decision_marks_deny() -> None:
    decision = PolicyDecision.deny("external write needs approval")
    out = format_kimi_decision(decision)
    hook = out["hookSpecificOutput"]
    assert hook["hookEventName"] == "PreToolUse"
    assert hook["permissionDecision"] == "deny"
    assert hook["permissionDecisionReason"] == "external write needs approval"


def test_format_kimi_decision_marks_allow_without_reason() -> None:
    out = format_kimi_decision(PolicyDecision.allow())
    hook = out["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow"
    assert "permissionDecisionReason" not in hook


def test_kimi_pre_tool_decision_reaches_the_hook_bridge() -> None:
    out = hook_bridge.format_pre_tool(
        "kimi", Decision.deny("external-write", "no remote writes in a trial")
    )
    assert out is not None
    hook = json.loads(out)["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    assert "no remote writes in a trial" in hook["permissionDecisionReason"]
    # An allow decision emits nothing (exit 0, silent).
    assert hook_bridge.format_pre_tool("kimi", Decision.allow()) is None


def test_hosts_kimi_capability_file_is_valid() -> None:
    data = json.loads((PLUGIN / "hosts" / "kimi.json").read_text(encoding="utf-8"))
    assert data["host"] == "kimi"
    assert data["product"]
    assert set(data["subagents"]) == {
        "start",
        "status",
        "follow_up",
        "cancel",
        "events",
    }
    assert all(not op["supported"] for op in data["subagents"].values())
    # Every claim is now backed by a verbatim first-party doc quote.
    for op in data["subagents"].values():
        provenance = op["provenance"]
        assert provenance["level"] == "first-party-doc"
        assert provenance["quote"]
        assert provenance["source"].startswith("https://")
    assert any("hook" in note for note in data["notes"])
