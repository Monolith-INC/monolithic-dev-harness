"""`harness tracker tree` rebuilds the local tracker's hierarchy from tickets filed by state."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness import local_tracker
from tests.harness.test_decisions import CLI
from tests.settings_fixture import write_settings


def _item(
    repo: Path, folder: str, key: str, kind: str, title: str, parent: str = ""
) -> None:
    root = local_tracker.storage_root(repo)
    local_tracker.write(
        root / folder / local_tracker.file_name(key, title),
        {"key": key, "kind": kind, "title": title, "parentId": parent},
    )


def _tree(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "tracker", "tree", "--repo", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_items_from_every_state_folder_are_drawn_under_their_parents(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    states = json.loads(
        (Path(__file__).parents[2] / "trackers/local/tracker.json").read_text()
    )["states"]
    new, active = states["backlog"], states["in_progress"]
    _item(tmp_path, new, "EPIC-0001", "epic", "Task persistence clarity")
    _item(tmp_path, new, "FEATURE-0002", "feature", "Reset notice", "EPIC-0001")
    _item(tmp_path, active, "STORY-0003", "user_story", "Explain reset", "FEATURE-0002")
    _item(tmp_path, new, "TASK-0005", "task", "Widget tests", "STORY-0003")
    _item(tmp_path, active, "TASK-0004", "task", "Add notice widget", "STORY-0003")
    _item(tmp_path, new, "TASK-0009", "task", "Stray task", "STORY-9999")
    draft = local_tracker.storage_root(tmp_path) / new / "draft-notes.md"
    draft.write_text("---\ntype: ticket\n---\n\nNot an item yet.\n", encoding="utf-8")

    shown = _tree(tmp_path)

    assert shown.returncode == 0, shown.stderr
    lines = shown.stdout.splitlines()
    assert lines[0].startswith("EPIC-0001")
    assert lines[1].startswith("└── FEATURE-0002")
    assert lines[2].startswith("    └── STORY-0003") and f"[{active}]" in lines[2]
    assert lines[3].startswith("        ├── TASK-0004")
    assert lines[4].startswith("        └── TASK-0005")
    assert (
        lines[5].startswith("TASK-0009") and "parent STORY-9999 not found" in lines[5]
    )
    assert len(lines) == 6, "a draft is not an item"


def test_an_empty_tracker_says_so(tmp_path: Path) -> None:
    write_settings(tmp_path)

    shown = _tree(tmp_path)

    assert shown.returncode == 0, shown.stderr
    assert "no work items yet" in shown.stdout
