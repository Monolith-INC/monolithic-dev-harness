"""First-run confirmation uses native controls before the repository is opted in."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import decisions, state
from tests.harness.test_decisions import CLI, native


def present(repo: Path, *transport: str) -> dict:
    return json.loads(
        subprocess.run(
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
            check=True,
            timeout=15,
        ).stdout
    )


@pytest.mark.parametrize("chosen", ["Yes", "No"])
def test_first_run_native_confirmation_is_captured(tmp_path: Path, chosen: str) -> None:
    match present(tmp_path, "--blocking-available"):
        case {"tool": "request_user_input", "questions": [offered]}:
            assert offered["question"] == "Confirm?"
            assert [option["label"] for option in offered["options"]] == ["Yes", "No"]
            native(
                tmp_path,
                "ask",
                {
                    "tool_name": "request_user_input",
                    "tool_use_id": "confirm-call",
                    "tool_input": {"questions": [offered]},
                },
            )
            native(
                tmp_path,
                "answer",
                {
                    "tool_use_id": "confirm-call",
                    "tool_input": {"questions": [offered]},
                    "tool_response": json.dumps(
                        {"answers": {offered["id"]: {"answers": [chosen]}}}
                    ),
                },
            )
            assert not decisions.waiting(tmp_path)
            assert decisions.record(tmp_path)["answer"] == chosen
            assert state.active_approval(tmp_path) is None
            assert not (tmp_path / ".harness/settings.json").exists()
        case _:
            pytest.fail("a native confirmation was not returned")


def test_async_confirmation_uses_buttons_instead_of_chat(tmp_path: Path) -> None:
    match present(tmp_path, "--async-available"):
        case {
            "tool": "request_user_input_async",
            "questions": [{"title": "Confirm?", "options": ["Yes", "No"]}],
            "wait": dict(),
        }:
            assert decisions.waiting(tmp_path)
        case _:
            pytest.fail("async availability must produce native buttons")
