"""A critic evaluates each submitted draft once; FAIL is not implementation authorization."""

import json
from pathlib import Path
from unittest.mock import patch

from orchestrator_core.engine import OrchestratorEngine

SKILLS = Path(__file__).resolve().parents[2] / "skills"


def test_invalid_draft_returns_report_once_without_authorization(tmp_path):
    engine = OrchestratorEngine(
        SKILLS,
        project_root=tmp_path,
        state_dir=tmp_path / ".harness/backlog",
        interactive=True,
    )
    with (
        patch(
            "orchestrator_core.draft_review.execute_handler",
            return_value={
                "ok": True,
                "outcome": "fail",
                "report": "Missing criteria",
                "critiques": ["missing"],
            },
        ) as critic,
        patch("builtins.input", side_effect=AssertionError("asked for implementation")),
    ):
        result = engine.run_tool_call("validate-artifact", {"draft_content": "bad"})
    assert result.ok
    assert critic.call_count == 1
    assert result.output["outcome"] == "fail"
    assert (
        json.loads(result.to_mcp_content()[0]["text"])["output"]["report"]
        == "Missing criteria"
    )


def test_revised_draft_can_be_reviewed_immediately(tmp_path):
    engine = OrchestratorEngine(
        SKILLS,
        project_root=tmp_path,
        state_dir=tmp_path / ".harness/backlog",
        quiet=True,
    )
    with patch(
        "orchestrator_core.draft_review.execute_handler",
        side_effect=[
            {"ok": True, "outcome": "fail", "critiques": ["missing"]},
            {"ok": True, "outcome": "pass", "critiques": []},
        ],
    ) as critic:
        assert (
            engine.run_tool_call("auto-fix-artifact", {"draft_content": "bad"}).output[
                "outcome"
            ]
            == "fail"
        )
        assert (
            engine.run_tool_call(
                "auto-fix-artifact", {"draft_content": "revised"}
            ).output["outcome"]
            == "pass"
        )
        assert critic.call_count == 2


def test_tool_error_preserves_findings(tmp_path):
    engine = OrchestratorEngine(
        SKILLS,
        project_root=tmp_path,
        state_dir=tmp_path / ".harness/backlog",
        quiet=True,
    )
    with patch(
        "orchestrator_core.draft_review.execute_handler",
        return_value={"ok": False, "error": "missing file", "report": "Unavailable"},
    ):
        result = engine.run_tool_call("validate-artifact", {"file_path": "missing"})
    assert not result.ok
    assert (
        json.loads(result.to_mcp_content()[0]["text"])["output"]["report"]
        == "Unavailable"
    )


def test_actual_reflection_history_and_fresh_cycle(tmp_path):
    engine = OrchestratorEngine(
        SKILLS,
        project_root=tmp_path,
        state_dir=tmp_path / ".harness/backlog",
        quiet=True,
    )
    args = {
        "draft_content": "---\ntype: user_story\ntitle: Count tasks\n---\nMissing all criteria.",
        "record_mistake": False,
    }
    first = engine.run_tool_call("auto-fix-artifact", args)
    assert first.ok and first.output["critiques"]
    second = engine.run_tool_call(
        "auto-fix-artifact", {**args, **first.output["reflection"]}
    )
    assert second.ok and second.output["blocked"]
    fresh = engine.run_tool_call(
        "auto-fix-artifact", {**args, "attempt": 0, "last_critiques": []}
    )
    assert fresh.ok and not fresh.output["blocked"]


def test_missing_file_is_tool_error_without_approval(tmp_path):
    engine = OrchestratorEngine(
        SKILLS,
        project_root=tmp_path,
        state_dir=tmp_path / ".harness/backlog",
        quiet=True,
    )
    assert not engine.run_tool_call(
        "validate-artifact", {"file_path": str(tmp_path / "missing.md")}
    ).ok
