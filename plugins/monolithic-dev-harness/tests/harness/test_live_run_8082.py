"""Regression cases from the 2026-10-16 live run on Story 8082, against a real project folder.

`harness next` reads the real facts (work session, answers, documents, local tracker) and names
the steps in route order; the guards refuse a Story's Tasks before its plan is approved and its
start before its Tasks exist; and the read-only commands the run was refused for are not writes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.result import Ok
from harness import (
    documents,
    gates,
    route_facts,
    rules,
    settings,
    state,
    work_sessions,
)
from integrations import registry
from integrations.contracts import WorkItemKind
from policy.commands import writes_code
from scripts import hook_runtime
from scripts.policy import CanonicalToolEvent
from tests.harness.test_discovery_render import prepare

DRAFT = (
    "O esforço feito em treino supervisionado teve como resultado melhorias na infraestrutura.\n\n"
    "1. Avaliar o que será aproveitado\n2. Medir o tempo total\n"
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    repo = prepare(tmp_path / "project")
    state.set_tracking_mode(repo, "enforced")
    return repo


def _ops(repo: Path):
    return registry.open_selected(repo, settings.load(repo)).value


def _session(repo: Path) -> work_sessions.Session:
    return work_sessions.start(repo, "Trabalhar na User Story 8082").value


def _answer(session: work_sessions.Session, gate: str, option: str) -> None:
    """Record the user's answer the way the answer hook saves it: the option's label."""
    _, catalog = gates.load().value
    label = next(o for o in catalog[gate].options if o.id == option).label["en"]
    history = session.folder / "decision-history.json"
    earlier = (state.read_json(history) or {}).get("answers", [])
    entry = {"gate": gate, "status": "answered", "answer": label}
    state.write_json(history, {"answers": [*earlier, entry]})


def _next(repo: Path, session: work_sessions.Session) -> dict:
    found = route_facts.next_for(repo, session.id)
    assert isinstance(found, Ok), found
    return found.value


def test_next_names_each_step_of_a_draft_story_in_order(project: Path) -> None:
    session = _session(project)
    assert _next(project, session)["step"] == "starting-item"

    story = (
        _ops(project)
        .create_work_item(
            WorkItemKind.USER_STORY, "Otimizar geração de análise via API", DRAFT, ""
        )
        .value
    )
    assert isinstance(work_sessions.track(project, session.id, story.key), Ok)
    session = work_sessions.select(project, session.id).value
    step = _next(project, session)
    # A draft is not asked about: discovery starts without a question.
    assert (step["step"], step["skill"], step["gate"]) == (
        "discovery",
        "bmad-build",
        "planning-depth",
    )

    _answer(session, "planning-depth", "standard")
    assert _next(project, session)["step"] == "planning-methods"
    _answer(session, "planning-methods", "shortlist")
    step = _next(project, session)
    assert step["step"] == "approach"
    assert (
        step["command"] == f"harness document path --type approach --item {story.key}"
    )

    approach = documents.document_path(
        project, _ops(project), story.key, "approach"
    ).value
    approach.parent.mkdir(parents=True, exist_ok=True)
    approach.write_text(
        "---\ntype: approach\nstatus: draft\n---\n# Approach\n", encoding="utf-8"
    )
    assert _next(project, session)["step"] == "hardening"

    _answer(session, "plan-checkpoint", "deepen")
    assert _next(project, session)["step"] == "hardening"
    _answer(session, "plan-checkpoint", "continue")
    step = _next(project, session)
    # The draft has no acceptance criteria: it is written in its template before any plan.
    assert (step["step"], step["skill"], step["gate"]) == (
        "refine-entry",
        "enrich-work-item",
        "publish-items",
    )
    assert [m["fact"] for m in step["missing"]] == ["entry_refined_now"]


def test_a_typed_answer_does_not_approve_the_approach(project: Path) -> None:
    session = _session(project)
    history = session.folder / "decision-history.json"
    state.write_json(
        history,
        {
            "answers": [
                {
                    "gate": "plan-checkpoint",
                    "status": "answered",
                    "answer": "i see no corrections",
                }
            ]
        },
    )
    found = route_facts.ProjectFacts(project, session).answers()
    assert found == {"plan-checkpoint": ""}


def _tracker_event(repo: Path, tool: str, arguments: dict) -> CanonicalToolEvent:
    return CanonicalToolEvent(
        client="claude", tool_name=tool, arguments=arguments, workspace_root=str(repo)
    )


def test_tasks_wait_for_the_approved_plan_and_the_start_for_the_tasks(
    project: Path,
) -> None:
    ops = _ops(project)
    story = ops.create_work_item(WorkItemKind.USER_STORY, "Example", DRAFT, "").value
    session = _session(project)

    tasks = hook_runtime.evaluate_event(
        _tracker_event(
            project,
            "tracker_create_work_item",
            {"kind": "task", "title": "Do it", "parentRef": story.key},
        ),
        session.id,
    )
    assert tasks.is_denied()
    assert "harness next" in tasks.reason

    start = hook_runtime.evaluate_event(
        _tracker_event(
            project,
            "tracker_transition_work_item",
            {"ref": story.key, "state": "in_progress"},
        ),
        session.id,
    )
    assert start.is_denied()
    assert "tasks_parented" in json.dumps(start.reason) or "Tasks" in start.reason

    feature = ops.create_work_item(WorkItemKind.FEATURE, "Container", DRAFT, "").value
    child = hook_runtime.evaluate_event(
        _tracker_event(
            project,
            "tracker_create_work_item",
            {"kind": "user_story", "title": "Child", "parentRef": feature.key},
        ),
        session.id,
    )
    assert not child.is_denied()


READ_ONLY = (
    # The run's `python3 -c` that only read a JSON file was refused as a human-owned write.
    'grep -n "^export" tools/a.ts | head -30; python3 -c "\n'
    "import json;d=json.load(open('tools/ANALYSIS_RULES.json'));print(list(d.keys()))\"",
    "head -40 tools/grading/grade_analysis_rules.py",
    # Editing the agent's own memory outside the project was refused as a governed change.
    "cd ~/.claude/projects/x/memory && sed -i 's#a#b#' MEMORY.md && grep -n latency MEMORY.md",
)


@pytest.mark.parametrize("command", READ_ONLY)
def test_reading_commands_from_the_run_are_not_writes(
    project: Path, command: str
) -> None:
    assert not rules.shell_writes_human_owned(command, project)
    assert not writes_code(command, project, None, "docs/planning")
