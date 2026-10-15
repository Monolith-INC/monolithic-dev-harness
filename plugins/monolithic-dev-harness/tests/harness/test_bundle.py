"""The final approval needs a refined, shown bundle; approved drafts are published once each."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import bundle, settings, state
from integrations import registry
from tests.harness.test_decisions import CLI
from tests.settings_fixture import write_settings

STORY = {
    "ref": "S1",
    "kind": "user_story",
    "title": "Explain reset on screen",
    "parent": "F1",
    "acceptance_criteria": ["The notice shows on the task screen"],
    "estimate": 2,
}
REFINED = {
    "items": [
        {"ref": "E1", "kind": "epic", "title": "Task persistence clarity"},
        {"ref": "F1", "kind": "feature", "title": "Reset notice", "parent": "E1"},
        STORY,
        {"ref": "T1", "kind": "task", "title": "Add notice widget", "parent": "S1"},
        {"ref": "T2", "kind": "task", "title": "Widget tests", "parent": "S1"},
    ]
}


def _manifest(repo: Path):
    write_settings(repo)
    return registry.selected(repo, settings.load(repo)).value.manifest


def _bundle(repo: Path, drafts: dict = REFINED) -> list[str]:
    folder = repo / "backlog" / "artifacts" / "work"
    folder.mkdir(parents=True)
    (folder / "plan.md").write_text("# Plan\n\n## Steps\n\nDo it.\n", encoding="utf-8")
    (folder / "tracker-drafts.json").write_text(json.dumps(drafts), encoding="utf-8")
    return [
        "backlog/artifacts/work/plan.md",
        "backlog/artifacts/work/tracker-drafts.json",
    ]


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args, "--repo", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _confirm(repo: Path, names: list[str]) -> subprocess.CompletedProcess[str]:
    return _cli(
        repo,
        "decision",
        "present",
        "--host",
        "claude",
        "--blocking-available",
        "--gate",
        "implementation-confirm",
        "--value",
        "story=S1",
        *(arg for name in names for arg in ("--artifact", name)),
    )


def test_a_refined_hierarchy_passes(tmp_path: Path) -> None:
    drafts = bundle._parse(REFINED).value
    assert isinstance(bundle.check_drafts(drafts, _manifest(tmp_path)), Ok)


@pytest.mark.parametrize(
    ("items", "problem"),
    [
        ([{**STORY, "parent": ""}], "S1: needs child tasks"),
        (
            [{**STORY, "parent": "", "acceptance_criteria": []}],
            "S1: needs acceptance criteria",
        ),
        (
            [{**STORY, "parent": "", "estimate": None}],
            "S1: needs an estimate",
        ),
        (
            [{"ref": "E1", "kind": "epic", "title": "Empty"}],
            "E1: a epic needs child items",
        ),
        (
            [
                {"ref": "E1", "kind": "epic", "title": "Epic"},
                {**STORY, "parent": "E1"},
                {"ref": "T1", "kind": "task", "title": "T", "parent": "S1"},
            ],
            "a epic cannot hold a user_story",
        ),
        ([{"ref": "T1", "kind": "task", "title": "Loose"}], "a task needs a parent"),
    ],
)
def test_unrefined_batches_name_what_is_missing(
    tmp_path: Path, items: list, problem: str
) -> None:
    drafts = bundle._parse({"items": items}).value

    checked = bundle.check_drafts(drafts, _manifest(tmp_path))

    assert isinstance(checked, Err) and problem in checked.failure.message


def test_a_story_may_hang_under_an_existing_tracker_item(tmp_path: Path) -> None:
    drafts = bundle._parse(
        {
            "items": [
                {**STORY, "parent": "FEATURE-0007"},
                {"ref": "T1", "kind": "task", "title": "T", "parent": "S1"},
            ]
        }
    ).value
    assert isinstance(bundle.check_drafts(drafts, _manifest(tmp_path)), Ok)


def test_final_approval_waits_for_refinement_and_for_the_bundle_to_be_shown(
    tmp_path: Path,
) -> None:
    _manifest(tmp_path)
    names = _bundle(tmp_path)

    unrefined = _confirm(tmp_path, names[:1])
    assert unrefined.returncode != 0 and "refine the work" in unrefined.stderr

    unshown = _confirm(tmp_path, names)
    assert unshown.returncode != 0 and "show the bundle first" in unshown.stderr

    shown = _cli(
        tmp_path, "workflow", "show", *(a for n in names for a in ("--artifact", n))
    )
    assert shown.returncode == 0, shown.stderr
    assert "Do it." in shown.stdout and "Add notice widget" in shown.stdout
    assert (
        "[backlog/artifacts/work/plan.md](backlog/artifacts/work/plan.md)"
        in shown.stdout
    )

    asked = _confirm(tmp_path, names)
    assert asked.returncode == 0, asked.stderr
    assert json.loads(asked.stdout)["tool"] == "AskUserQuestion"


def test_a_file_changed_after_showing_must_be_shown_again(tmp_path: Path) -> None:
    _manifest(tmp_path)
    names = _bundle(tmp_path)
    assert (
        _cli(
            tmp_path, "workflow", "show", *(a for n in names for a in ("--artifact", n))
        ).returncode
        == 0
    )

    (tmp_path / names[0]).write_text("# Plan\n\nSomething else.\n", encoding="utf-8")

    assert "show the bundle first" in _confirm(tmp_path, names).stderr


def test_approved_drafts_are_created_once_each_under_their_parents(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    names = _bundle(tmp_path)
    drafts_name = names[1]

    refused = _cli(tmp_path, "tracker", "publish", "--drafts", drafts_name)
    assert refused.returncode != 0 and "not part of an approved" in refused.stderr

    digest = bundle._digests(tmp_path, [drafts_name]).value[0][1]
    state.write_json(
        state.state_dir(tmp_path) / "decision-history.json",
        {
            "answers": [
                {
                    "gate": "implementation-confirm",
                    "status": "answered",
                    "answer": "Approve",
                    "artifacts": [[drafts_name, digest]],
                }
            ]
        },
    )

    first = _cli(tmp_path, "tracker", "publish", "--drafts", drafts_name)
    again = _cli(tmp_path, "tracker", "publish", "--drafts", drafts_name)

    assert first.returncode == 0, first.stderr
    assert first.stdout.count("→") == 5
    assert "nothing to do" in again.stdout
    tree = _cli(tmp_path, "tracker", "tree")
    lines = tree.stdout.splitlines()
    assert lines[0].startswith("EPIC-") and lines[1].startswith("└── FEATURE-")
    assert lines[2].lstrip().startswith("└── STORY-")
    assert sum(line.lstrip(" │├└─").startswith("TASK-") for line in lines) == 2
    assert manifest.name == "local"


@pytest.mark.parametrize("later", ["Revise", "Stop here"])
def test_a_later_answer_withdraws_the_approval_to_publish(
    tmp_path: Path, later: str
) -> None:
    """Only the session's last implementation-confirm answer counts, as for code changes."""
    _manifest(tmp_path)
    drafts_name = _bundle(tmp_path)[1]
    digest = bundle._digests(tmp_path, [drafts_name]).value[0][1]
    answer = {
        "gate": "implementation-confirm",
        "status": "answered",
        "artifacts": [[drafts_name, digest]],
    }
    state.write_json(
        state.state_dir(tmp_path) / "decision-history.json",
        {"answers": [{**answer, "answer": "Approve"}, {**answer, "answer": later}]},
    )

    refused = _cli(tmp_path, "tracker", "publish", "--drafts", drafts_name)

    assert refused.returncode != 0 and "not part of an approved" in refused.stderr


def test_approving_other_drafts_last_does_not_publish_these(tmp_path: Path) -> None:
    _manifest(tmp_path)
    drafts_name = _bundle(tmp_path)[1]
    digest = bundle._digests(tmp_path, [drafts_name]).value[0][1]
    approved = {
        "gate": "implementation-confirm",
        "status": "answered",
        "answer": "Approve",
    }
    state.write_json(
        state.state_dir(tmp_path) / "decision-history.json",
        {
            "answers": [
                {**approved, "artifacts": [[drafts_name, digest]]},
                {**approved, "artifacts": [["other/tracker-drafts.json", "0" * 64]]},
            ]
        },
    )

    refused = _cli(tmp_path, "tracker", "publish", "--drafts", drafts_name)

    assert refused.returncode != 0 and "not part of an approved" in refused.stderr


def _transcript(path: Path, reply: str) -> Path:
    rows = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": "harness workflow show --artifact plan.md"
                        },
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": reply}]},
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def test_on_claude_the_bundle_must_be_in_the_reply_not_only_a_tool_result(
    tmp_path: Path,
) -> None:
    from tests.harness.test_question_fallback import claude_hook

    _manifest(tmp_path)
    names = _bundle(tmp_path)
    shown = _cli(
        tmp_path, "workflow", "show", *(a for n in names for a in ("--artifact", n))
    )
    asked = json.loads(_confirm(tmp_path, names).stdout)
    question = {
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": asked["questions"]},
    }

    summary = _transcript(tmp_path / "summary.jsonl", "The plan is ready. Approve?")
    denied = claude_hook(
        tmp_path,
        "ask",
        {**question, "tool_use_id": "toolu_a", "transcript_path": str(summary)},
    )
    assert "bundle-not-shown" in denied

    full = _transcript(tmp_path / "full.jsonl", shown.stdout)
    allowed = claude_hook(
        tmp_path,
        "ask",
        {**question, "tool_use_id": "toolu_b", "transcript_path": str(full)},
    )
    assert "deny" not in allowed
