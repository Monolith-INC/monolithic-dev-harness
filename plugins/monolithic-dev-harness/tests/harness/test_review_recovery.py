"""Failed decisions cannot orphan checkpoints; interrupted projections recover once."""

from dataclasses import asdict

import pytest

from core.result import Err, Ok, err
from harness import decisions, review_decisions, state, workflow
from tests.harness.test_discovery_render import prepare, session


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    repo = prepare(tmp_path / "project")
    return repo, session(repo).id


def ask(repo, scope, key="review"):
    return review_decisions.begin(
        repo,
        key,
        "Use this plan?",
        ("Continue", "Revise"),
        "chat",
        (("plan.md", "digest"),),
        work_session_id=scope,
    )


def test_an_existing_question_cannot_create_an_orphan_checkpoint(context):
    repo, scope = context
    assert isinstance(
        decisions.begin(
            repo,
            "old",
            "Keep this choice?",
            ("Yes", "No"),
            "chat",
            work_session_id=scope,
        ),
        Ok,
    )
    before = workflow.load(repo, scope).value
    assert isinstance(ask(repo, scope), Err)
    assert workflow.load(repo, scope) == Ok(before)
    assert decisions.pending(repo, scope).id == "old"


def test_failed_decision_write_leaves_workflow_untouched(context, monkeypatch):
    repo, scope = context
    before = workflow.load(repo, scope).value
    original = state.write_json

    def fail_decision(path, payload):
        match path.name:
            case "decision.json":
                raise OSError("decision storage unavailable")
            case _:
                return original(path, payload)

    monkeypatch.setattr(state, "write_json", fail_decision)
    assert isinstance(ask(repo, scope), Err)
    assert workflow.load(repo, scope) == Ok(before)
    assert decisions.pending(repo, scope) is None


def test_checkpoint_write_failure_recovers_without_duplicate(context, monkeypatch):
    repo, scope = context
    original = state.write_json

    def fail_workflow(path, payload):
        match path.name:
            case "workflow.json":
                raise OSError("checkpoint storage unavailable")
            case _:
                return original(path, payload)

    with monkeypatch.context() as fault:
        fault.setattr(state, "write_json", fail_workflow)
        assert isinstance(ask(repo, scope), Err)
        assert decisions.pending(repo, scope).id == "review"
        assert review_decisions.RECOVERY in decisions.record(repo, scope)
        assert isinstance(workflow.load(repo, scope), Err)
    recovered = workflow.load(repo, scope).value
    assert recovered.current.pending == "Use this plan?"
    assert len(recovered.points) == 2
    assert review_decisions.RECOVERY not in decisions.record(repo, scope)
    assert isinstance(ask(repo, scope, "retry"), Err)
    assert workflow.load(repo, scope) == Ok(recovered)


def test_cleanup_failure_recognizes_already_applied_checkpoint(context, monkeypatch):
    repo, scope = context
    original = state.write_json

    def fail_cleanup(path, payload):
        match path.name, review_decisions.RECOVERY in payload:
            case "decision.json", False:
                raise OSError("cleanup storage unavailable")
            case _:
                return original(path, payload)

    with monkeypatch.context() as fault:
        fault.setattr(state, "write_json", fail_cleanup)
        assert isinstance(ask(repo, scope), Err)
        assert len(state.read_json(workflow.path(repo, scope))["points"]) == 2
    assert len(workflow.load(repo, scope).value.points) == 2
    assert review_decisions.RECOVERY not in decisions.record(repo, scope)


def test_recovery_refuses_to_overwrite_unrelated_workflow_changes(context, monkeypatch):
    repo, scope = context
    before = workflow.load(repo, scope).value
    with monkeypatch.context() as fault:
        fault.setattr(
            review_decisions, "_project", lambda *_: err("fault", "interrupted")
        )
        assert isinstance(ask(repo, scope), Err)
    changed = workflow.add_point(before, "Other progress", "build").value
    state.write_json(workflow.path(repo, scope), asdict(changed))
    assert isinstance(workflow.load(repo, scope), Err)
    assert workflow.from_dict(state.read_json(workflow.path(repo, scope))) == Ok(
        changed
    )
    assert decisions.pending(repo, scope).id == "review"


def test_answer_capture_recovers_checkpoint_before_resolving(context, monkeypatch):
    repo, scope = context
    (repo / "plan.md").write_text("Reviewed content")
    original = state.write_json

    def fail_workflow(path, payload):
        match path.name:
            case "workflow.json":
                raise OSError("interrupted projection")
            case _:
                return original(path, payload)

    with monkeypatch.context() as fault:
        fault.setattr(state, "write_json", fail_workflow)
        assert isinstance(
            review_decisions.begin(
                repo,
                "review",
                "Use this plan?",
                ("Continue", "Revise"),
                "chat",
                (("plan.md", workflow.file_digest(repo / "plan.md").value),),
                work_session_id=scope,
            ),
            Err,
        )
        assert isinstance(
            decisions.resolve(
                repo, "review", "Continue", "chat", work_session_id=scope
            ),
            Err,
        )
        assert decisions.pending(repo, scope).id == "review"
    assert isinstance(
        decisions.resolve(repo, "review", "Continue", "chat", work_session_id=scope), Ok
    )
    assert len(workflow.load(repo, scope).value.points) == 2
    assert decisions.record(repo, scope)["answer"] == "Continue"


def test_process_interruption_after_decision_commit_recovers(context, monkeypatch):
    repo, scope = context

    def power_loss(*_):
        raise SystemExit(77)

    with monkeypatch.context() as fault:
        fault.setattr(review_decisions, "_project", power_loss)
        with pytest.raises(SystemExit):
            ask(repo, scope)
    assert decisions.pending(repo, scope).id == "review"
    assert len(workflow.load(repo, scope).value.points) == 2
    assert review_decisions.RECOVERY not in decisions.record(repo, scope)


@pytest.mark.parametrize("field,value", (("artifacts", 7), ("review_checkpoint", None)))
def test_corrupt_recovery_returns_failure_without_overwriting_workflow(
    context, monkeypatch, field, value
):
    repo, scope = context
    before = workflow.load(repo, scope).value
    with monkeypatch.context() as fault:
        fault.setattr(
            review_decisions, "_project", lambda *_: err("fault", "interrupted")
        )
        assert isinstance(ask(repo, scope), Err)
    saved = decisions.record(repo, scope)
    state.write_json(
        workflow.path(repo, scope).with_name("decision.json"), {**saved, field: value}
    )
    assert isinstance(workflow.load(repo, scope), Err)
    assert workflow.from_dict(state.read_json(workflow.path(repo, scope))) == Ok(before)
