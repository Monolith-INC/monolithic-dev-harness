"""Where discovery stands is read from the documents on its Epic, never stored.

Each test builds ROOT on the local tracker (no server) and publishes the documents of one state.
The table is the routing of `modes/discovery/workflow.md`: the first row that holds is the step.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from core.result import Err, Ok, err
from harness import cli, documents_catalog, mode_hooks, modes, routing, settings, state
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

    def __init__(self, ops: TrackerOps, repo: Path) -> None:
        self.ops = ops
        self.repo = repo
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
    return Epic(opened.value, tmp_path)


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


# the real mode: `harness modes step`, and the step in each prompt's orientation


def enter(epic: Epic, root: str | None = None) -> modes.Active:
    """Enter the real discovery mode on ROOT, as the skill does."""
    entered = modes.enter(
        epic.repo, "discovery", root=epic.root if root is None else root
    )
    assert isinstance(entered, Ok), entered
    return entered.value


def run_step(epic: Epic, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    capsys.readouterr()
    code = cli.main(["modes", "step", "--repo", str(epic.repo)])
    out, error = capsys.readouterr()
    return code, out, error


def test_modes_step_prints_the_step_of_the_active_mode(
    epic: Epic, capsys: pytest.CaptureFixture[str]
) -> None:
    active = enter(epic)
    epic.publish("vision-doc", render("vision-doc"))
    expected = epic.step()

    code, out, _ = run_step(epic, capsys)

    assert code == 0
    assert json.loads(out) == {
        "mode": "discovery",
        "root": epic.root,
        "step": "gate-g1",
        "detail": expected.detail,
    }
    assert active.session_id not in out


def test_modes_step_with_no_root_yet_is_step_one(
    epic: Epic, capsys: pytest.CaptureFixture[str]
) -> None:
    enter(epic, root="")

    code, out, _ = run_step(epic, capsys)

    assert code == 0
    assert json.loads(out)["step"] == "vision"
    assert json.loads(out)["root"] == ""


def test_modes_step_follows_the_documents_as_they_are_published(
    epic: Epic, capsys: pytest.CaptureFixture[str]
) -> None:
    enter(epic)
    epic.publish("vision-doc", render("vision-doc", status="Approved"))

    assert json.loads(run_step(epic, capsys)[1])["step"] == "prd"

    epic.publish("prd", render("prd", status="Approved"))

    assert json.loads(run_step(epic, capsys)[1])["step"] == "exit"


def test_modes_step_outside_a_mode_is_refused(
    epic: Epic, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, error = run_step(epic, capsys)

    assert code == 2 and out == ""
    assert json.loads(error)["error"] == "mode_inactive"


def test_modes_step_says_when_the_epic_cannot_be_read(
    epic: Epic, capsys: pytest.CaptureFixture[str]
) -> None:
    enter(epic, root="EPIC-9999")

    code, out, error = run_step(epic, capsys)

    assert code == 2 and out == ""
    assert "EPIC-9999" in json.loads(error)["message"]


def test_modes_step_says_the_harness_is_suspended_instead_of_a_step(
    epic: Epic, capsys: pytest.CaptureFixture[str]
) -> None:
    enter(epic)
    state.set_harness_mode(epic.repo, "suspended")

    code, out, error = run_step(epic, capsys)

    assert code == 0 and out == ""
    assert error.strip() == cli.SUSPENDED


def test_a_mode_with_no_steps_has_none_to_read(epic: Epic) -> None:
    active = enter(epic)

    match routing.current(epic.repo, replace(active, mode="other")):
        case Err(failure):
            assert failure.code == "no_steps"
        case other:
            raise AssertionError(f"expected a failure, got {other!r}")


def test_the_prompt_orientation_gives_the_step_routing_finds(epic: Epic) -> None:
    enter(epic)
    epic.publish("vision-doc", render("vision-doc", empty=("Constraints",)))
    found = epic.step()
    assert found.kind == "vision-resume"

    oriented = mode_hooks.orient(epic.repo)

    assert oriented.notice == ""
    assert oriented.text is not None
    assert f"Current step: {routing.describe(found)}\n" in oriented.text
    assert "Rules:\n" in oriented.text
    assert "LIST ROOT's artifacts" in oriented.text


def test_the_orientation_follows_the_step_as_the_documents_change(epic: Epic) -> None:
    enter(epic)
    before = mode_hooks.orient(epic.repo).text
    epic.publish("vision-doc", render("vision-doc", status="Approved"))

    after = mode_hooks.orient(epic.repo).text

    assert before is not None and after is not None
    assert "Current step: Step 1, Vision Doc:" in before
    assert "Current step: Step 2, PRD:" in after


def test_the_orientation_says_in_one_line_when_the_step_cannot_be_read_and_goes_on(
    epic: Epic,
) -> None:
    enter(epic, root="EPIC-9999")

    oriented = mode_hooks.orient(epic.repo)

    assert oriented.text is not None
    (line,) = [
        line for line in oriented.text.splitlines() if line.startswith("Current step")
    ]
    assert line.startswith("Current step: could not be read")
    assert "EPIC-9999" in line
    assert "LIST ROOT's artifacts" in oriented.text


def test_the_orientation_never_raises_when_reading_the_step_blows_up(
    epic: Epic, monkeypatch: pytest.MonkeyPatch
) -> None:
    enter(epic)

    def explode(repo: Path, active: modes.Active) -> None:
        raise RuntimeError("the tracker fell over")

    monkeypatch.setattr(routing, "current", explode)

    oriented = mode_hooks.orient(epic.repo)

    assert oriented.text is not None
    assert "Current step: could not be read (" in oriented.text
    assert "the tracker fell over" in oriented.text
    assert "Rules:\n" in oriented.text
