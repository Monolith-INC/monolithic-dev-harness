"""A Story as the route leaves it before it starts: refined, with approved preparation documents
and a reading manifest. Tests that exercise code changes or completion start from here."""

from __future__ import annotations

from pathlib import Path

from harness import documents, local_artifacts, state
from integrations.contracts import TrackerOps, WorkItemChanges, WorkItemKind
from tests.harness.test_plan_review import REFINED

TITLE = "Explain what a settings reset removes"


def refined_story(ops: TrackerOps, parent: str = "") -> str:
    """A Story whose text passes validate-artifact; returns its key."""
    key = ops.create_work_item(
        WorkItemKind.USER_STORY, TITLE, REFINED, parent
    ).value.key
    ops.update_work_item(key, WorkItemChanges(story_points=2))
    return key


def prepared(root: Path, ops: TrackerOps, key: str, folder: Path) -> None:
    """Approve the Story's risk and verification documents and write its reading manifest."""
    notes = []
    for kind in ("risk-assessment", "verification-plan"):
        note = folder / "Preparation" / f"{kind}-{key.lower()}.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            f'---\ntype: {kind}\nstory: "{key}"\nstatus: draft\n---\n\n# {kind}\n',
            encoding="utf-8",
        )
        notes.append(str(note))
    approval = "HB-PREP" + key.replace("-", "")[-4:]
    state.open_approval(root, approval, 20)
    state.pin_notes(root, approval, local_artifacts.reviewed_notes(root, notes))
    manifest = documents.document_path(root, ops, key, "reading-manifest").value
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("# Prepared artifact manifest\n", encoding="utf-8")
