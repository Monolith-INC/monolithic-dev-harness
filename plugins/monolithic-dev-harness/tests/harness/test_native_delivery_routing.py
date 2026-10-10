"""Exercise manifest routing too, instead of bypassing it with direct hook calls."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from harness import decisions
from host_adapters.interactions import question_transport
from tests.harness.test_codex_answer_capture import question
from tests.harness.test_decisions import CLI, native
from tests.settings_fixture import write_settings


@pytest.mark.parametrize(
    "name",
    [
        "request_user_input",
        "functions.request_user_input",
        "request_user_input_async",
        "functions.request_user_input_async",
    ],
)
def test_manifest_routes_native_controls(name):
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "hooks/codex.hooks.json").read_text()
    )
    assert all(
        any(
            re.fullmatch(rule["matcher"], name)
            and any("--event " + event in h["command"] for h in rule["hooks"])
            for rule in manifest["hooks"][phase]
        )
        for phase, event in [("PreToolUse", "ask"), ("PostToolUse", "answer")]
    )
    assert question_transport("codex", name) == (
        "async" if name.endswith("_async") else "blocking"
    )


@pytest.mark.parametrize("name", ["functions.request_user_input", "request_user_input"])
def test_namespaced_same_workspace_capture(tmp_path, name):
    write_settings(tmp_path)
    payload = {
        "tool_name": name,
        "tool_use_id": "actual-call",
        "tool_input": question(),
    }
    native(tmp_path, "ask", payload)
    native(
        tmp_path,
        "answer",
        {
            **payload,
            "tool_response": json.dumps(
                {"answers": {"next_step": {"answers": ["Prepare work items"]}}}
            ),
        },
    )
    saved = decisions.record(tmp_path)
    assert saved["status"] == "answered"
    assert saved["answer"] == "Prepare work items"


@pytest.mark.parametrize(
    "flags,transport",
    [
        ((), "blocking"),
        (("--native-unavailable",), "chat"),
        (("--async-available",), "async"),
    ],
)
def test_codex_presentation_attempts_native_before_chat(tmp_path, flags, transport):
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(tmp_path),
            "--host",
            "codex",
            "--question",
            "How should we proceed?",
            "--option",
            "Continue",
            "--option",
            "Pause",
            *flags,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["transport"] == transport
