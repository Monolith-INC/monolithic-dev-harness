"""Answering a plan approval never reaches the tracker; the tracker check leaves a local receipt.

The plan's tracker-backed checks run when the question is prepared (`harness decision present`)
and again on `harness plan check <story>`. Each run that passes writes a receipt. The answer hook
reads local files only, and a code write waits while the approved plan has no current receipt.
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, plan_review, rules, settings, work_sessions, workflow
from harness.workflow_evidence import item_digest
from integrations import gateway_client, registry
from integrations.contracts import WorkItemChanges
from tests.harness.test_plan_review import _cli, _confirm, _plan, _project, _show

QUESTION = "Approve this implementation plan?"
OPTIONS = ("Approve", "Revise", "Stop here")


class TrackerReached(Exception):
    """Neither an OSError nor a ValueError, so nothing on the answer path can swallow it."""


def _no_tracker(monkeypatch: pytest.MonkeyPatch) -> None:
    def reached(*_args, **_kwargs):
        raise TrackerReached("the answer path reached the tracker")

    monkeypatch.setattr(registry, "_transport", reached)
    monkeypatch.setattr(gateway_client, "open_selected", reached)


def _sourced_plan(repo: Path, story: str) -> str:
    """A plan that names the digest of its Story's current requirements."""
    ops = registry.open_selected(repo, settings.load(repo)).value
    plan = _plan(repo, story)
    target = repo / plan
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "status: draft",
            "status: draft\nsource_digest: "
            + item_digest(ops.get_work_item(story).value),
        ),
        encoding="utf-8",
    )
    return plan


def _pending(repo: Path, transport: str = "chat") -> tuple[str, str, str]:
    """A pending `implementation-confirm` in a session that tracks the plan's Story."""
    story = _project(repo)
    scope = work_sessions.create(repo, "Plan story").value.id
    assert isinstance(work_sessions.track(repo, scope, story), Ok)
    plan = _sourced_plan(repo, story)
    assert isinstance(
        decisions.begin(
            repo,
            "d1",
            QUESTION,
            OPTIONS,
            transport,
            ((plan, workflow.file_digest(repo / plan).value),),
            approval=True,
            gate="implementation-confirm",
            work_session_id=scope,
        ),
        Ok,
    )
    return story, scope, plan


def test_an_answer_is_recorded_while_the_tracker_cannot_be_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, scope, _ = _pending(tmp_path)
    _no_tracker(monkeypatch)

    result = decisions.resolve(tmp_path, "d1", "Approve", "chat", work_session_id=scope)

    assert isinstance(result, Ok), result
    assert (decisions.record(tmp_path, scope) or {})["answer"] == "Approve"


def test_the_prompt_hook_records_the_approval_without_the_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness import hook

    _, scope, _ = _pending(tmp_path)
    _no_tracker(monkeypatch)
    monkeypatch.setattr(
        sys, "stdin", StringIO(json.dumps({"cwd": str(tmp_path), "prompt": "Approve"}))
    )

    assert hook.main(["--host", "codex", "--event", "prompt"]) == 0

    assert "human decision recorded: Approve" in capsys.readouterr().out
    assert (decisions.record(tmp_path, scope) or {})["status"] == "answered"


def test_a_changed_plan_is_still_refused_from_local_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, scope, plan = _pending(tmp_path)
    _no_tracker(monkeypatch)
    (tmp_path / plan).write_text("something else\n", encoding="utf-8")

    refused = decisions.resolve(
        tmp_path, "d1", "Approve", "chat", work_session_id=scope
    )

    assert "reviewed artifact changed" in refused.failure.message
    assert decisions.waiting(tmp_path, scope)


def test_preparing_the_question_writes_the_receipt(tmp_path: Path) -> None:
    story = _project(tmp_path)
    plan = _sourced_plan(tmp_path, story)
    assert _show(tmp_path, plan).returncode == 0

    asked = _confirm(tmp_path, plan)

    assert asked.returncode == 0, asked.stderr
    receipt = plan_review.receipt(tmp_path, story)
    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    assert receipt["story_digest"] == item_digest(ops.get_work_item(story).value)
    assert receipt["plan"] == plan
    assert receipt["plan_digest"] == workflow.file_digest(tmp_path / plan).value
    assert receipt["checked"]


def test_plan_check_rereads_the_tracker_and_rewrites_the_receipt(
    tmp_path: Path,
) -> None:
    story = _project(tmp_path)
    plan = _sourced_plan(tmp_path, story)
    scope = work_sessions.create(tmp_path, "Plan story").value.id
    assert plan_review.receipt(tmp_path, story) is None

    checked = _cli(tmp_path, "plan", "check", story)

    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["story"] == story
    assert plan_review.receipt(tmp_path, story)["plan"] == plan

    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    ops.update_work_item(story, WorkItemChanges(description="Changed requirements"))
    refused = _cli(tmp_path, "plan", "check", story)

    assert refused.returncode != 0
    assert plan_review.receipt(tmp_path, story) is None
    assert scope


def test_plan_check_still_inspects_a_plan_file(tmp_path: Path) -> None:
    story = _project(tmp_path)
    plan = _plan(tmp_path, story)

    inspected = _cli(tmp_path, "plan", "check", plan)

    assert json.loads(inspected.stdout)["scope"] == "advisory_only"


def _write(repo: Path, name: str) -> rules.ToolCall:
    return rules.make_call(
        "Write",
        {"file_path": str(repo / name), "content": "x = 1\n"},
        kind="edit",
        file_paths=(str(repo / name),),
    )


def _approved(repo: Path) -> tuple[str, str, str]:
    story, scope, plan = _pending(repo)
    assert isinstance(
        decisions.resolve(repo, "d1", "Approve", "chat", work_session_id=scope), Ok
    )
    return story, scope, plan


def test_code_waits_while_the_approved_plan_has_no_current_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    story, scope, plan = _approved(tmp_path)
    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    _no_tracker(monkeypatch)

    denied = rules.rule_plan_checked(_write(tmp_path, "app.py"), tmp_path, scope)
    assert not denied.allowed and denied.rule == "plan-checked"
    assert f"harness plan check {story}" in denied.reason
    # The plan itself and other notes are never code.
    assert rules.rule_plan_checked(_write(tmp_path, plan), tmp_path, scope).allowed

    assert isinstance(plan_review.verify(tmp_path, [plan], ops, scope), Ok)
    assert rules.rule_plan_checked(_write(tmp_path, "app.py"), tmp_path, scope).allowed

    target = tmp_path / plan
    target.write_text(target.read_text() + "\nOne more step.\n", encoding="utf-8")
    assert not rules.rule_plan_checked(
        _write(tmp_path, "app.py"), tmp_path, scope
    ).allowed


def test_a_session_with_no_approved_plan_is_not_held(tmp_path: Path) -> None:
    _, scope, _ = _pending(tmp_path)

    assert rules.rule_plan_checked(_write(tmp_path, "app.py"), tmp_path, scope).allowed
    assert rules.rule_plan_checked(_write(tmp_path, "app.py"), tmp_path, None).allowed


def test_a_receipt_uses_only_the_tracker_revision_that_was_validated(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    story, scope, plan = _pending(tmp_path)
    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    original = ops.get_work_item(story).value
    newer = replace(original, description=original.description + "\nNew requirements")
    reads = []

    def changing_item(key):
        assert key == story
        reads.append(key)
        return Ok(original if len(reads) < 3 else newer)

    changing_ops = replace(ops, get_work_item=changing_item)
    assert isinstance(plan_review.verify(tmp_path, [plan], changing_ops, scope), Ok)
    assert plan_review.receipt(tmp_path, story)["story_digest"] == item_digest(original)
    assert len(reads) == 1
