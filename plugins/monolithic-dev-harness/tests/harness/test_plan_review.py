"""A Story's implementation plan is approved on its own, after it was shown as it reads now."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from harness import settings
from integrations import registry
from integrations.contracts import WorkItemKind
from tests.harness.test_decisions import CLI
from tests.settings_fixture import write_settings

PLAN = "Vault/Implementation_Plans/plan.md"


def _project(repo: Path) -> str:
    """A local tracker holding one Story; returns its key."""
    write_settings(repo, artifacts_path="Vault")
    ops = registry.open_selected(repo, settings.load(repo)).value
    return ops.create_work_item(
        WorkItemKind.USER_STORY, "Explain reset", "", ""
    ).value.key


def _plan(
    repo: Path,
    story: str,
    kind: str = "implementation-plan",
    status: str = "approved",
    body: str = "# Plan\n\n## Steps\n\nDo it.\n",
) -> str:
    path = repo / PLAN
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntype: {kind}\nstory: "{story}"\nstatus: {status}\n---\n\n{body}',
        encoding="utf-8",
    )
    return PLAN


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args, "--repo", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _show(repo: Path, *names: str) -> subprocess.CompletedProcess[str]:
    return _cli(
        repo, "workflow", "show", *(a for n in names for a in ("--artifact", n))
    )


def _confirm(repo: Path, story: str, *names: str) -> subprocess.CompletedProcess[str]:
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
        f"story={story}",
        *(a for n in names for a in ("--artifact", n)),
    )


def test_a_shown_plan_for_a_tracked_story_may_be_approved(tmp_path: Path) -> None:
    story = _project(tmp_path)
    plan = _plan(tmp_path, story)

    shown = _show(tmp_path, plan)
    assert shown.returncode == 0, shown.stderr
    assert "Do it." in shown.stdout
    assert f"[{plan}]({plan})" in shown.stdout and story in shown.stdout

    asked = _confirm(tmp_path, story, plan)
    assert asked.returncode == 0, asked.stderr
    assert json.loads(asked.stdout)["tool"] == "AskUserQuestion"


def test_the_plan_must_be_shown_as_it_reads_now(tmp_path: Path) -> None:
    story = _project(tmp_path)
    plan = _plan(tmp_path, story)
    assert "show the plan first" in _confirm(tmp_path, story, plan).stderr

    assert _show(tmp_path, plan).returncode == 0
    _plan(tmp_path, story, body="# Plan\n\nSomething else.\n")
    assert "show the plan first" in _confirm(tmp_path, story, plan).stderr


def test_exactly_one_plan_is_approved_at_a_time(tmp_path: Path) -> None:
    story = _project(tmp_path)
    plan = _plan(tmp_path, story)
    other = tmp_path / "Vault" / "other.md"
    other.write_text("notes\n", encoding="utf-8")

    assert "--artifact" in _confirm(tmp_path, story).stderr
    assert (
        "one implementation plan"
        in _confirm(tmp_path, story, plan, "Vault/other.md").stderr
    )


def test_the_note_must_be_an_approved_plan_for_that_story(tmp_path: Path) -> None:
    story = _project(tmp_path)

    _plan(tmp_path, story, kind="design-doc")
    assert "type implementation-plan" in _confirm(tmp_path, story, PLAN).stderr

    _plan(tmp_path, story, status="draft")
    assert "status: approved" in _confirm(tmp_path, story, PLAN).stderr

    _plan(tmp_path, "STORY-0042")
    assert f"names STORY-0042, not {story}" in _confirm(tmp_path, story, PLAN).stderr


def test_the_story_must_exist_in_the_tracker(tmp_path: Path) -> None:
    _project(tmp_path)
    plan = _plan(tmp_path, "STORY-0042")
    assert _show(tmp_path, plan).returncode == 0

    refused = _confirm(tmp_path, "STORY-0042", plan)
    assert refused.returncode != 0 and "STORY-0042" in refused.stderr


def test_tracker_publish_is_gone(tmp_path: Path) -> None:
    _project(tmp_path)
    refused = _cli(tmp_path, "tracker", "publish")
    assert refused.returncode == 2 and "invalid choice" in refused.stderr


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
                            "command": f"harness workflow show --artifact {PLAN}"
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


def test_on_claude_the_plan_must_be_in_the_reply_not_only_a_tool_result(
    tmp_path: Path,
) -> None:
    from tests.harness.test_question_fallback import claude_hook

    story = _project(tmp_path)
    plan = _plan(tmp_path, story)
    shown = _show(tmp_path, plan)
    asked = json.loads(_confirm(tmp_path, story, plan).stdout)
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
    assert "plan-not-shown" in denied

    full = _transcript(tmp_path / "full.jsonl", shown.stdout)
    allowed = claude_hook(
        tmp_path,
        "ask",
        {**question, "tool_use_id": "toolu_b", "transcript_path": str(full)},
    )
    assert "deny" not in allowed
