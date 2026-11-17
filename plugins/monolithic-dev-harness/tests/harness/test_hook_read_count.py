"""A hook reads the same number of files and folders whatever the size of the project.

A hook may only read a small, fixed set of local records. Each event runs in this process in a
small project (10 source files, 1 ended work session) and in a large one (many source files,
1,000 ended work sessions), once to warm up (imports, caches) and once counted. Counted are the
files opened for reading and the folders listed; nothing is blocked.

`STILL_GROWING` lists the events whose count differs between the two projects today. The later
tasks of the plan that cut the hook path off from the project walk, the tracker and the session
list remove their entries, and the set must be empty at the end. A new grower fails the test, and
so does an entry that no longer grows: the set only shrinks and stays exact.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from harness import work_sessions
from tests.harness.test_hook_budget import _run
from tests.harness.test_hook_invariants import _question
from tests.settings_fixture import write_settings

SMALL_FILES = 10
LARGE_FILES = 10_000
SMALL_SESSIONS = 1
LARGE_SESSIONS = 1_000
FOLDERS = 100

# Every entry grows with the number of ended work sessions (about 2.3 files and 3 folders each,
# 4 folders each before a code edit), not with the number of source files: no event here reaches
# the project walk, because none has a manual-check question or a Story with a receipt pending
# (T3 and T6 remove the walks, which this test cannot yet reach). The cause is the same for all:
# `work_sessions.list_sessions` reads every session ever made (through `decisions.any_waiting`
# and the routing of each event). It goes with mode 4's session list in the plan's section for
# modes (tasks F), which this section's tasks do not touch. Emptied at the end of the plan.
STILL_GROWING: frozenset[str] = frozenset(
    {
        "ask",
        "answer",
        "pre-tool: code edit",  # also reads the tracker in the gate: T3
        "pre-tool: shell command",
        "prompt",  # also the mode step read: T5
        "stop",
    }
)


@dataclass(frozen=True)
class Reads:
    files: int = 0
    folders: int = 0

    def __str__(self) -> str:
        return f"{self.files} files, {self.folders} folders"


def _opens_for_reading(mode: object) -> bool:
    return isinstance(mode, str) and not set(mode) & set("wax+")


@contextlib.contextmanager
def _counting() -> Iterator[list[str]]:
    """Wrap, never block: every open for reading and every folder listing is noted and delegated."""
    seen: list[str] = []
    real = {
        "open": builtins.open,
        "io_open": io.open,
        "os_open": os.open,
        "scandir": os.scandir,
        "listdir": os.listdir,
    }

    def opened(target):
        def wrapper(file, mode="r", *args, **kwargs):
            seen.extend(["file"] if _opens_for_reading(mode) else [])
            return target(file, mode, *args, **kwargs)

        return wrapper

    def os_opened(path, flags, *args, **kwargs):
        seen.extend(["file"] if flags & os.O_ACCMODE == os.O_RDONLY else [])
        return real["os_open"](path, flags, *args, **kwargs)

    def listed(target):
        def wrapper(*args, **kwargs):
            seen.append("folder")
            return target(*args, **kwargs)

        return wrapper

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(builtins, "open", opened(real["open"]))
        patch.setattr(io, "open", opened(real["io_open"]))
        patch.setattr(os, "open", os_opened)
        patch.setattr(os, "scandir", listed(real["scandir"]))
        patch.setattr(os, "listdir", listed(real["listdir"]))
        yield seen


def _project(root: Path, files: int, sessions: int) -> Path:
    write_settings(root)
    per_folder = max(1, files // FOLDERS)
    for number in range(files):
        source = root / "src" / f"pkg{number // per_folder}" / f"mod{number}.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"VALUE = {number}\n", encoding="utf-8")
    for number in range(sessions):
        identifier = f"WS-{number:012x}"
        folder = root.resolve() / work_sessions.ROOT / identifier
        folder.mkdir(parents=True)
        (folder / "session.json").write_text(
            json.dumps(
                {
                    "version": work_sessions.VERSION,
                    "id": identifier,
                    "project_root": str(root.resolve()),
                    "request": f"Work {number}",
                    "status": "complete",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-02T00:00:00+00:00",
                    "events": [
                        {"type": "started", "at": "2026-01-01T00:00:00+00:00"},
                        {"type": "completed", "at": "2026-01-02T00:00:00+00:00"},
                    ],
                }
            ),
            encoding="utf-8",
        )
    return root


def _answered(asked: dict) -> dict:
    first = asked["questions"][0]["question"]
    return {**asked, "answers": {first: "Approve"}}


def _events(repo: Path) -> dict[str, tuple[str, dict]]:
    """Each event with a realistic payload (host claude), in the order a conversation goes."""
    asked = _question()
    question = {
        "tool_name": "AskUserQuestion",
        "tool_use_id": "toolu_1",
        "session_id": "conversation",
    }
    return {
        "pre-tool: code edit": (
            "pre-tool",
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(repo / "src" / "pkg0" / "mod0.py"),
                    "old_string": "VALUE = 0",
                    "new_string": "VALUE = 1",
                },
                "session_id": "conversation",
            },
        ),
        "pre-tool: shell command": (
            "pre-tool",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls -la"},
                "session_id": "conversation",
            },
        ),
        "prompt": ("prompt", {"prompt": "go on", "session_id": "conversation"}),
        "ask": ("ask", {**question, "tool_input": asked}),
        "answer": (
            "answer",
            {
                **question,
                "tool_input": _answered(asked),
                "tool_response": _answered(asked),
            },
        ),
        "stop": (
            "stop",
            {"last_assistant_message": "Done.", "session_id": "conversation"},
        ),
    }


def _count(repo: Path, event: str, payload: dict) -> Reads:
    with _counting() as seen:
        _run(repo, event, payload, host="claude")
    return Reads(seen.count("file"), seen.count("folder"))


def _measure(repo: Path) -> dict[str, Reads]:
    """Every event once to warm up, then once counted, in the same order both times."""
    events = _events(repo)
    for event, payload in events.values():
        _run(repo, event, payload, host="claude")
    return {
        name: _count(repo, event, payload) for name, (event, payload) in events.items()
    }


def test_every_event_reads_the_same_number_of_files_whatever_the_project_size(
    tmp_path: Path,
) -> None:
    small = _measure(_project(tmp_path / "small", SMALL_FILES, SMALL_SESSIONS))
    large = _measure(_project(tmp_path / "large", LARGE_FILES, LARGE_SESSIONS))

    growing = frozenset(name for name in small if small[name] != large[name])
    table = "\n".join(
        f"    {name}: small {small[name]} | large {large[name]}" for name in small
    )

    assert growing == STILL_GROWING, (
        f"Reads per event, {SMALL_FILES} files and {SMALL_SESSIONS} ended session against "
        f"{LARGE_FILES} files and {LARGE_SESSIONS} ended sessions:\n{table}\n"
        f"New growers, not allowed (read a fixed set of records): "
        f"{sorted(growing - STILL_GROWING) or '(none)'}\n"
        f"Stale entries, no longer growing (delete them from STILL_GROWING): "
        f"{sorted(STILL_GROWING - growing) or '(none)'}"
    )
