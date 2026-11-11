"""Where discovery stands is read from the documents on its Epic, never stored.

Each test builds ROOT on the local tracker (no server) and publishes the documents of one state.
The table is the routing of `modes/discovery/workflow.md`: the first row that holds is the step.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.result import Err, Ok, err
from harness import documents_catalog, routing, settings
from integrations import registry
from integrations.contracts import ArtifactDraft, TrackerOps, WorkItemKind
from tests.settings_fixture import write_settings

PROJECT = "Atlas"
CATALOG = documents_catalog.load().value
VISION, PRD = CATALOG["vision-doc"], CATALOG["prd"]


def render(
    kind: str,
    status: str = "Draft",
    empty: tuple[str, ...] = (),
    missing: tuple[str, ...] = (),
    bare_tbd: tuple[str, ...] = (),
    reasoned_tbd: tuple[str, ...] = (),
) -> str:
    """A document of the catalog with every section filled except the ones named."""
    document = CATALOG[kind]
    lines = [f"# {document.title.format(project=PROJECT)}", "", f"Status: {status}", ""]
    for section in document.sections:
        if section in missing:
            continue
        body = (
            ""
            if section in empty
            else "TBD"
            if section in bare_tbd
            else "TBD — waiting on finance (owner: Ana)"
            if section in reasoned_tbd
            else "Real content."
        )
        lines += [f"## {section}", "", body, ""]
    return "\n".join(lines)


class Epic:
    """ROOT on the local tracker, with the documents published on it so far."""

    def __init__(self, ops: TrackerOps) -> None:
        self.ops = ops
        self.root = ops.create_work_item(WorkItemKind.EPIC, PROJECT, "", "").value.key

    def publish(self, kind: str, content: str, revision: str = "r1") -> None:
        title = CATALOG[kind].title.format(project=PROJECT) if kind in CATALOG else kind
        added = self.ops.add_artifact(
            self.root, ArtifactDraft(kind, title, content, revision)
        )
        assert isinstance(added, Ok), added

    def step(self) -> routing.Step:
        match routing.step(self.ops, self.root):
            case Ok(found):
                return found
            case failed:
                raise AssertionError(f"routing failed: {failed!r}")


@pytest.fixture
def epic(tmp_path: Path) -> Epic:
    write_settings(tmp_path)
    opened = registry.open_selected(tmp_path, settings.load(tmp_path))
    assert isinstance(opened, Ok), opened
    return Epic(opened.value)


# the routing table, one row per test


def test_no_root_is_step_one(epic: Epic) -> None:
    found = routing.step(epic.ops, "")

    assert found == Ok(
        routing.Step(
            "vision", "there is no discovery Epic (ROOT) yet: interview the user first"
        )
    )


def test_a_root_with_no_vision_doc_is_step_one(epic: Epic) -> None:
    found = epic.step()

    assert found.kind == "vision"
    assert epic.root in found.detail


def test_a_vision_doc_with_an_empty_section_resumes_step_one(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", empty=("Constraints",)))

    found = epic.step()

    assert found.kind == "vision-resume"
    assert "Constraints (placeholder)" in found.detail
    assert "r1" in found.detail


def test_a_vision_doc_with_a_missing_section_resumes_step_one(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", missing=("Out of Scope",)))

    found = epic.step()

    assert found.kind == "vision-resume"
    assert "Out of Scope (missing)" in found.detail


def test_a_complete_vision_doc_that_is_not_approved_is_gate_g1(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc"))

    found = epic.step()

    assert found.kind == "gate-g1"
    assert "r1" in found.detail


def test_an_approved_vision_doc_with_no_prd_is_step_two(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"))

    found = epic.step()

    assert found.kind == "prd"
    assert "no PRD" in found.detail


def test_a_prd_with_an_incomplete_section_is_step_two(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"))
    epic.publish("prd", render("prd", empty=("Risks",), missing=("KPIs",)))

    found = epic.step()

    assert found.kind == "prd"
    assert "Risks (placeholder)" in found.detail
    assert "KPIs (missing)" in found.detail


def test_a_complete_prd_that_is_not_approved_is_gate_g2(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"))
    epic.publish("prd", render("prd"))

    found = epic.step()

    assert found.kind == "gate-g2"
    assert "r1" in found.detail


def test_an_approved_prd_is_the_exit(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"))
    epic.publish("prd", render("prd", status="Approved"))

    found = epic.step()

    assert found.kind == "exit"
    assert "harness modes leave" in found.detail


# first true row wins


def test_a_prd_published_before_its_vision_doc_was_approved_still_waits_at_gate_g1(
    epic: Epic,
) -> None:
    epic.publish("vision-doc", render("vision-doc"))
    epic.publish("prd", render("prd", status="Approved"))

    assert epic.step().kind == "gate-g1"


def test_an_approved_prd_that_lost_a_section_goes_back_to_step_two(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"))
    epic.publish("prd", render("prd", status="Approved", empty=("NFRs",)))

    assert epic.step().kind == "prd"


# sections: what counts as complete


def test_a_bare_tbd_is_incomplete(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", bare_tbd=("Success Metrics",)))

    found = epic.step()

    assert found.kind == "vision-resume"
    assert "Success Metrics (placeholder)" in found.detail


def test_a_tbd_with_its_reason_and_owner_is_complete(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", reasoned_tbd=("Success Metrics",)))

    assert epic.step().kind == "gate-g1"


# the latest revision of each kind is the one that counts


def test_the_latest_revision_decides_even_when_an_earlier_one_was_approved(
    epic: Epic,
) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"), "r1")
    epic.publish("vision-doc", render("vision-doc"), "r2")

    found = epic.step()

    assert found.kind == "gate-g1"
    assert "r2" in found.detail


def test_revisions_are_ordered_by_number_not_as_text(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc", status="Approved"), "r10")
    epic.publish("vision-doc", render("vision-doc"), "r2")

    assert epic.step().kind == "prd"


def test_a_revision_numbered_without_a_prefix_is_ordered_too(epic: Epic) -> None:
    epic.publish("vision-doc", render("vision-doc"), "1")
    epic.publish("vision-doc", render("vision-doc", status="Approved"), "2")

    assert epic.step().kind == "prd"


def test_other_kinds_on_root_do_not_count_as_a_discovery_document(epic: Epic) -> None:
    epic.publish("design-brief", "# Design Brief\n\n## Anything\n\ntext\n")

    assert epic.step().kind == "vision"


# the tracker cannot be read


def test_a_tracker_that_cannot_list_the_artifacts_is_a_failure_not_a_step(
    epic: Epic,
) -> None:
    unreadable = replace(
        epic.ops, list_artifacts=lambda ref: err("tracker_unreachable", "no answer")
    )

    match routing.step(unreadable, epic.root):
        case Err(failure):
            assert failure.code == "tracker_unreachable"
        case other:
            raise AssertionError(f"expected a failure, got {other!r}")


def test_the_step_reads_nothing_but_the_artifacts_of_root(epic: Epic) -> None:
    asked: list[str] = []

    def listed(ref: str):
        asked.append(ref)
        return Ok(())

    routing.step(replace(epic.ops, list_artifacts=listed), epic.root)

    assert asked == [epic.root]
