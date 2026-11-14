"""A manual check is confirmed with a native question, not a typed phrase (issue #50).

`harness decision present --gate manual-check --value checks=<names>` pins the code as it is when
the question is shown; Confirm records each named check for that code."""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness import code_content, gates, state
from tests.harness.test_approval_scope import project
from tests.harness.test_decisions import CLI, native

CHECKS = ("functions-suite", "emulator-flows")


def _ask(repo: Path, session: str) -> None:
    subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--session-id",
            session,
            "--gate",
            "manual-check",
            "--value",
            f"checks={', '.join(CHECKS)}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


def _recorded(repo: Path, code: str) -> list[bool]:
    return [state.has_manual(repo, name, code) for name in CHECKS]


def test_confirming_records_every_named_check_for_the_current_code(
    tmp_path: Path,
) -> None:
    session, _ = project(tmp_path)
    _ask(tmp_path, session)
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "Confirm"})
    assert _recorded(tmp_path, code_content.current(tmp_path)) == [True, True]


def test_not_now_records_nothing(tmp_path: Path) -> None:
    session, _ = project(tmp_path)
    _ask(tmp_path, session)
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "Not now"})
    assert _recorded(tmp_path, code_content.current(tmp_path)) == [False, False]


def test_a_code_change_after_the_question_records_nothing(tmp_path: Path) -> None:
    session, _ = project(tmp_path)
    shown = code_content.current(tmp_path)
    _ask(tmp_path, session)
    (tmp_path / "main.py").write_text("print('changed')\n")
    native(tmp_path, "prompt", {"session_id": "native-a", "prompt": "Confirm"})
    assert _recorded(tmp_path, shown) == [False, False]
    assert _recorded(tmp_path, code_content.current(tmp_path)) == [False, False]


def test_a_tracker_status_with_underscores_reads_as_words() -> None:
    rendered = gates.render(
        "move-item",
        "en",
        {"item": "Story 8270", "status": "in_progress", "ref": "8270"},
    ).value
    assert rendered.question == "Move Story 8270 to in progress?"
