"""Exercise manifest routing too, instead of bypassing it with direct hook calls."""

import io
import json
import re
import subprocess
from pathlib import Path

import pytest

from harness import decisions, hook
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
def test_manifest_routes_native_controls(name, tmp_path, monkeypatch):
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "hooks/codex.hooks.json").read_text()
    )
    assert all(
        any(
            re.fullmatch(rule["matcher"], name)
            and any("--event " + event in h["command"] for h in rule["hooks"])
            for rule in manifest["hooks"][phase]
        )
        for phase, event in [("PreToolUse", "pre-tool"), ("PostToolUse", "answer")]
    )
    routed = []
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path), "tool_name": name}))
    )
    monkeypatch.setattr(
        hook,
        "handle_ask",
        lambda host, payload: routed.append((host, payload["tool_name"])) or 0,
    )
    assert hook.main(["--host", "codex", "--event", "pre-tool"]) == 0
    assert routed == [("codex", name)]
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
    native(tmp_path, "pre-tool", payload)
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
        ((), "chat"),
        (("--native-unavailable",), "chat"),
        (("--async-available",), "chat"),
    ],
)
def test_codex_unobserved_presentation_does_not_infer_mode_from_flags(
    tmp_path, flags, transport
):
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
    assert not json.loads(result.stdout)["structured_qualified"]
