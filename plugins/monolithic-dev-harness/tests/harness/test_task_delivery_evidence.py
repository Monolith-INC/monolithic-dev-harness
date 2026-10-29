"""Task completion requires its own current deliverables and verification."""

import hashlib
import json

from hook_runtime import _task_completion

from harness import local_artifacts, settings, state, work_sessions, workflow
from integrations import registry
from integrations.contracts import ArtifactDraft, WorkItemKind
from tests.settings_fixture import write_settings


def project(repo):
    write_settings(repo, artifacts_path="Vault")
    ops = registry.open_selected(repo, settings.load(repo)).value
    story = ops.create_work_item(
        WorkItemKind.USER_STORY, "Read canonical series", "", ""
    ).value
    task = ops.create_work_item(
        WorkItemKind.TASK, "Review the literature", "", story.id
    ).value
    current = work_sessions.create(repo, "Review series").value
    work_sessions.link(repo, current.id, story.key)
    return ops, story, task, current


def test_linked_parent_without_task_evidence_is_denied(tmp_path):
    ops, _, task, _ = project(tmp_path)
    assert _task_completion(tmp_path, ops, task).is_denied()


def test_approved_noncode_deliverable_can_complete_and_changes_invalidate_it(tmp_path):
    ops, story, task, current = project(tmp_path)
    plan = tmp_path / "Vault/plan.md"
    plan.parent.mkdir()
    plan.write_text(
        f'---\ntype: implementation-plan\nstory: "{story.key}"\n---\nReview the literature.\n'
    )
    deliverable = tmp_path / "Vault/reading.md"
    deliverable.write_text(
        f'---\ntype: literature-review\nstory: "{story.key}"\n---\nA documented rule.\n'
    )
    state.open_approval(tmp_path, "approved-documents", 10)
    state.pin_notes(
        tmp_path,
        "approved-documents",
        local_artifacts.reviewed_notes(tmp_path, (str(plan), str(deliverable))),
    )
    ops.add_artifact(
        task.key,
        ArtifactDraft(
            "verification",
            "Task delivery",
            json.dumps(
                {
                    "task": task.key,
                    "work_session": current.id,
                    "plan": "Vault/plan.md",
                    "step": "Review the literature.",
                    "plan_digest": workflow.document_digest(plan.read_bytes()),
                    "deliverables": {
                        "Vault/reading.md": hashlib.sha256(
                            deliverable.read_bytes()
                        ).hexdigest()
                    },
                    "checks": [],
                    "manual": [],
                }
            ),
            "1",
        ),
    )
    assert not _task_completion(tmp_path, ops, task).is_denied()
    deliverable.write_text(deliverable.read_text() + "Changed after approval.\n")
    assert _task_completion(tmp_path, ops, task).is_denied()
