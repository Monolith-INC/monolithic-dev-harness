"""Approval binds source requirements, not incidental state/revision fields."""

from core.result import Err, Ok
from harness import plan_review, settings, work_sessions
from harness.workflow_evidence import item_digest
from integrations import registry
from integrations.contracts import LogicalState, WorkItemChanges
from tests.harness.test_plan_review import _plan, _project


def test_managed_plan_rejects_changed_requirements_but_keeps_same_content(tmp_path):
    story = _project(tmp_path)
    scope = work_sessions.create(tmp_path, "Plan story").value.id
    plan = _plan(tmp_path, story)
    ops = registry.open_selected(tmp_path, settings.load(tmp_path)).value
    assert isinstance(plan_review.source_matches(tmp_path, [plan], ops, scope), Err)
    target = tmp_path / plan
    target.write_text(
        target.read_text().replace(
            "status: draft",
            "status: draft\nsource_digest: "
            + item_digest(ops.get_work_item(story).value),
        )
    )
    assert plan_review.source_matches(tmp_path, [plan], ops, scope) == Ok(None)
    ops.transition_work_item(story, LogicalState.IN_PROGRESS)
    assert plan_review.source_matches(tmp_path, [plan], ops, scope) == Ok(None)
    ops.update_work_item(
        story, WorkItemChanges(description="A changed acceptance criterion")
    )
    assert isinstance(plan_review.source_matches(tmp_path, [plan], ops, scope), Err)
