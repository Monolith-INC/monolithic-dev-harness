"""A damaged host-session link is repaired by an explicit switch, through the real hook."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions
from host_adapters import work_session_context
from tests.harness.test_approval_scope import project
from tests.harness.test_decisions import native

HARNESS = str(Path(__file__).resolve().parents[2] / "bin" / "harness")
DAMAGE = {
    "invalid-json": lambda link, _: link.write_text("{", encoding="utf-8"),
    "wrong-version": lambda link, _: link.write_text(
        json.dumps({"version": 99}), encoding="utf-8"
    ),
    "missing-session": lambda link, record: link.write_text(
        json.dumps({**record, "work_session_id": "WS-gone"}), encoding="utf-8"
    ),
    "unreadable": lambda link, _: link.chmod(0),
}


def bash(repo: Path, command: str) -> str:
    return native(
        repo,
        "pre-tool",
        {
            "session_id": "native-a",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )


def link(repo: Path) -> Path:
    return (
        repo
        / work_session_context.ROOT
        / "codex"
        / (hashlib.sha256(b"native-a").hexdigest() + ".json")
    )


@pytest.mark.parametrize("damage", sorted(DAMAGE))
def test_a_damaged_link_is_repaired_only_by_an_explicit_switch(
    tmp_path: Path, damage: str
) -> None:
    if damage == "unreadable" and os.geteuid() == 0:
        pytest.skip("root reads files without permission")
    _, second = project(tmp_path)
    source = link(tmp_path)
    DAMAGE[damage](source, json.loads(source.read_text(encoding="utf-8")))

    refused = bash(tmp_path, "touch notes.txt")
    assert "work-session-context" in refused and "work-session select" in refused
    assert "deny" not in bash(tmp_path, f"{HARNESS} work-session select {second}")

    assert work_session_context.resolve_session(tmp_path, "codex", "native-a") == Ok(
        second
    )
    kept = tuple(source.parent.glob(source.stem + ".damaged-*.json"))
    assert len(kept) == 1


def test_a_switch_through_a_damaged_link_cannot_escape_a_waiting_question(
    tmp_path: Path,
) -> None:
    first, second = project(tmp_path)
    assert isinstance(
        decisions.begin(
            tmp_path,
            "d1",
            "Continue?",
            ("Continue", "Stop"),
            "chat",
            work_session_id=first,
        ),
        Ok,
    )
    link(tmp_path).write_text("{", encoding="utf-8")

    assert "deny" in bash(tmp_path, f"{HARNESS} work-session select {second}")
    assert "deny" not in bash(tmp_path, f"{HARNESS} work-session select {first}")
    assert work_session_context.resolve_session(tmp_path, "codex", "native-a") == Ok(
        first
    )
