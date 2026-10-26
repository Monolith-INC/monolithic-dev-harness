"""Selections survive interruption; proposed method results never accept themselves."""

from core.result import Err
from harness.elicitation import SelectionState


def test_selection_addition_is_ordered_and_reopening_preserves_it():
    from harness.elicitation import SelectionEvent, SelectionState, reduce_selection

    selected = reduce_selection(
        SelectionState(), SelectionEvent("add", ("first", "audit"))
    ).value
    assert selected.selected == ("first", "audit")
    assert reduce_selection(
        selected, SelectionEvent("add", ("audit", "edges"))
    ).value.selected == ("first", "audit", "edges")
    finished = reduce_selection(selected, SelectionEvent("finish")).value
    assert finished.phase == "apply"
    assert reduce_selection(finished, SelectionEvent("reopen")).value.selected == (
        "first",
        "audit",
    )
    complete = SelectionState(
        selected=("first",),
        outcomes=(("first", "apply", "review.md", "digest"),),
        phase="hardening",
    )
    reopened = reduce_selection(complete, SelectionEvent("reopen")).value
    assert (
        reduce_selection(reopened, SelectionEvent("finish")).value.phase == "hardening"
    )


def test_full_catalog_keeps_finish_control_after_a_selection(tmp_path):
    from harness import elicitation_store, work_sessions
    from harness.elicitation import SelectionEvent, reduce_selection

    current = work_sessions.create(tmp_path, "Choose review methods").value
    selected = reduce_selection(
        SelectionState(mode="catalog"), SelectionEvent("add", ("1",))
    ).value
    elicitation_store.save(tmp_path, current.id, selected)
    staged = elicitation_store.present_selection(tmp_path, current.id).value
    assert "Finish selection" in staged["options"]
    assert (
        reduce_selection(selected, SelectionEvent("add", ("2",))).value.mode
        == "catalog"
    )


def test_hardening_reviews_must_match_approved_approach(tmp_path):
    from core.result import Ok
    from harness import elicitation_store, work_sessions

    current = work_sessions.create(tmp_path, "Review approach").value
    tuple(
        (tmp_path / name).write_text(name)
        for name in ("review.md", "triage.md", "approach.md", "other.md")
    )
    assert isinstance(
        elicitation_store.record_hardening(
            tmp_path, current.id, "readiness", "review.md", "triage.md", "approach.md"
        ),
        Ok,
    )
    assert elicitation_store.hardening_ready(
        tmp_path, current, "light", ("approach.md",)
    )
    assert not elicitation_store.hardening_ready(
        tmp_path, current, "light", ("other.md",)
    )


def test_durable_method_selection_satisfies_route_selection_fact(tmp_path):
    from harness import elicitation_store, route_facts, work_sessions

    current = work_sessions.create(tmp_path, "Choose methods").value
    elicitation_store.save(
        tmp_path, current.id, SelectionState(selected=("1",), phase="apply")
    )
    assert route_facts.ProjectFacts(tmp_path, current).check("methods_selected", None)
    assert not route_facts.ProjectFacts(tmp_path, current).check(
        "methods_applied", None
    )


def test_result_requires_matching_human_decision_and_current_file(tmp_path):
    from harness import elicitation_store as elicitation
    from harness import work_sessions

    current = work_sessions.create(tmp_path, "Read series").value
    proposal = tmp_path / "method.md"
    proposal.write_text("First principles findings and proposed changes.\n")
    elicitation.save(
        tmp_path, current.id, SelectionState(selected=("1",), phase="apply")
    )
    assert elicitation.stage_result(tmp_path, current.id, "method.md").value[
        "options"
    ] == ("Apply", "Reject", "Give direction")
    assert elicitation.load(tmp_path, current.id).value.outcomes == ()
    assert isinstance(
        elicitation.capture(tmp_path, current.id, {"id": "wrong", "answer": "Apply"}),
        Err,
    )


def test_real_prepared_choice_records_selection_once_and_preserves_pending(
    tmp_path, capsys
):
    from harness import cli, decisions, work_sessions
    from harness import elicitation_store as elicitation

    current = work_sessions.create(tmp_path, "Read series").value
    common = ["--repo", str(tmp_path), "--session-id", current.id, "--host", "text"]
    assert (
        cli.main(
            ["elicitation", "start", *common, "--method-id", "1", "--method-id", "2"]
        )
        == 0
    )
    assert cli.main(["elicitation", "present", *common]) == 0
    pending = decisions.record(tmp_path, current.id)
    assert pending["elicitation"] == {"revision": 0}
    assert isinstance(elicitation.present_selection(tmp_path, current.id), Err)
    assert (
        decisions.resolve(
            tmp_path,
            pending["id"],
            "Tree of Thoughts",
            "chat",
            work_session_id=current.id,
        ).value["status"]
        == "answered"
    )
    assert elicitation.load(tmp_path, current.id).value.selected == ("1",)
    assert cli.main(["elicitation", "present", *common]) == 0
    finish = decisions.record(tmp_path, current.id)
    decisions.resolve(
        tmp_path, finish["id"], "Finish selection", "chat", work_session_id=current.id
    )
    assert elicitation.load(tmp_path, current.id).value.phase == "apply"
    assert cli.main(["elicitation", "reopen", *common]) == 0
    reopen = decisions.record(tmp_path, current.id)
    assert elicitation.load(tmp_path, current.id).value.phase == "apply"
    decisions.resolve(
        tmp_path, reopen["id"], "Reopen selection", "chat", work_session_id=current.id
    )
    assert elicitation.load(tmp_path, current.id).value.phase == "choose"
    assert elicitation.load(tmp_path, current.id).value.selected == ("1",)
