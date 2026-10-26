"""First-run confirmation preserves decisions until native evidence or typed recovery."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, state
from host_adapters.codex_runtime import persist_observation
from tests.harness.test_decisions import CLI, native


def present(repo: Path, *transport: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--host",
            "codex",
            "--question",
            "Confirm?",
            "--option",
            "Yes",
            "--option",
            "No",
            *transport,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


@pytest.mark.parametrize("chosen", ["Yes", "No"])
def test_first_run_unknown_mode_preserves_typed_recovery(
    tmp_path: Path, chosen: str
) -> None:
    assert present(tmp_path, "--blocking-available").returncode == 0
    assert decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"prompt": chosen})
    assert not decisions.waiting(tmp_path)
    assert decisions.record(tmp_path)["answer"] == chosen
    assert state.active_approval(tmp_path) is None
    assert not (tmp_path / ".harness/settings.json").exists()


def test_async_confirmation_requires_observation_not_flags(
    tmp_path: Path, monkeypatch
) -> None:
    # Synthetic fixture follows the captured native hook shape; it is not live UI evidence.
    assert isinstance(
        persist_observation(
            tmp_path,
            {
                "session_id": "synthetic-root",
                "turn_id": "synthetic-turn",
                "model": "test-model",
                "tool_name": "request_user_input_async",
                "hook_event_name": "PreToolUse",
            },
        ),
        Ok,
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "synthetic-root")
    match json.loads(present(tmp_path, "--async-available").stdout):
        case {
            "tool": "request_user_input_async",
            "questions": [{"title": "Confirm?", "options": ["Yes", "No"]}],
            "wait": None,
            "structured_qualified": False,
        }:
            assert decisions.waiting(tmp_path)
        case _:
            pytest.fail("observed async delivery must preserve the pending question")
