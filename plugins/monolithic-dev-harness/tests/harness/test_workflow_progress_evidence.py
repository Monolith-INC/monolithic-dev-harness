"""A human approval is permission; route progress requires the resulting verified effect."""

from core.result import Err
from harness import questions, route_facts, state, work_sessions, workflow_evidence
from integrations import gateway
from tests.settings_fixture import write_settings


def session(repo):
    write_settings(repo)
    return work_sessions.create(repo, "Repair visual analysis").value


def history(repo, current):
    return state.write_json(
        current.folder / "decision-history.json",
        {
            "answers": [
                {
                    "id": "approach",
                    "gate": "plan-checkpoint",
                    "status": "answered",
                    "answer": "Approve and continue",
                },
                {
                    "id": "publish",
                    "gate": "publish-items",
                    "status": "answered",
                    "answer": "Approve (Recommended)",
                    "binds": {
                        "values": {
                            "count": "1",
                            "items": "title:Canonical visual reading",
                        }
                    },
                },
            ]
        },
    )


def test_publication_approval_alone_is_not_publication(tmp_path):
    current = session(tmp_path)
    history(tmp_path, current)
    assert not route_facts.ProjectFacts(tmp_path, current).check("any_published", None)
    assert not route_facts.ProjectFacts(tmp_path, current).check(
        "published_after_approach", None
    )


def test_successful_write_and_readback_record_actual_publication(tmp_path):
    current = session(tmp_path)
    history(tmp_path, current)
    state.open_approval(
        tmp_path, questions.approval_id("publish"), 20, work_session_id=current.id
    )
    gateway.handle_call(
        "tracker_create_work_item",
        {"kind": "user_story", "title": "Canonical visual reading"},
        tmp_path,
    )
    assert route_facts.ProjectFacts(tmp_path, current).check("any_published", None)
    receipt = workflow_evidence.publications(current)[0]
    history(tmp_path, current)
    answers = (state.read_json(current.folder / "decision-history.json") or {})[
        "answers"
    ]
    state.write_json(
        current.folder / "decision-history.json",
        {
            "answers": [
                answers[0],
                {
                    **answers[1],
                    "binds": {"values": {"count": "1", "items": "key:unapproved-key"}},
                },
            ]
        },
    )
    assert not route_facts.ProjectFacts(tmp_path, current).check(
        "published_after_approach", None
    )
    state.write_json(
        current.folder / "decision-history.json",
        {
            "answers": [
                answers[0],
                {
                    **answers[1],
                    "binds": {
                        "values": {
                            "count": "1",
                            "items": "title:Canonical visual reading",
                        }
                    },
                },
            ]
        },
    )
    assert route_facts.ProjectFacts(tmp_path, current).check(
        "published_after_approach", None
    )
    from harness import settings
    from integrations import registry
    from integrations.contracts import WorkItemChanges

    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    ops.update_work_item(
        receipt["item"], WorkItemChanges(description="Changed after approval")
    )
    assert not route_facts.ProjectFacts(tmp_path, current).check(
        "published_after_approach", None
    )


def test_missing_depth_blocks_final_approach_gate(tmp_path):
    from harness.workflow_evidence import gate_ready

    current = session(tmp_path)
    assert isinstance(gate_ready(tmp_path, current.id, "plan-checkpoint"), Err)


def test_rework_does_not_reuse_an_old_rounds_approach_or_depth(tmp_path):
    current = session(tmp_path)
    state.write_json(
        current.folder / "decision-history.json",
        {
            "answers": [
                {
                    "id": "depth-old",
                    "gate": "planning-depth",
                    "status": "answered",
                    "answer": "Standard (Recommended)",
                },
                {
                    "id": "approach-old",
                    "gate": "plan-checkpoint",
                    "status": "answered",
                    "answer": "Approve and continue",
                },
                {
                    "id": "rework-now",
                    "gate": "refined-start",
                    "status": "answered",
                    "answer": "Rework it",
                },
            ]
        },
    )
    facts = route_facts.ProjectFacts(tmp_path, current)
    assert facts.answer("planning-depth") is None
    assert facts.answer("plan-checkpoint") is None
