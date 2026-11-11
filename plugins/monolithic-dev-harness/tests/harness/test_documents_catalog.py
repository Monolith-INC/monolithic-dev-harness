"""The document catalog defines each discovery document once, and refuses a mapping that does not line up."""

from __future__ import annotations

from pathlib import Path

from core.result import Err, Ok
from harness import documents_catalog

VISION_SECTIONS = (
    "Problem Statement",
    "Target Users",
    "Desired Outcome",
    "Business Objectives",
    "Success Metrics",
    "Constraints",
    "Out of Scope",
    "Open Questions",
    "Next Step",
    "Change history",
)
PRD_SECTIONS = (
    "User Problem",
    "Personas",
    "Business Goals",
    "User Journeys",
    "Functional Requirements",
    "NFRs",
    "Out of Scope",
    "Dependencies",
    "Risks",
    "KPIs",
    "Open Questions",
    "Next Step",
    "Change history",
)
VISION_INTERVIEW = (
    "Problem",
    "Target users",
    "Desired outcome",
    "Business objectives",
    "Success metrics with baseline",
    "Constraints",
    "Out of scope",
)

BASE = """
[vision-doc]
title = "Vision Doc — {project}"
sections = ["Problem Statement", "Open Questions"]
interview = ["Problem"]

[prd]
title = "PRD — {project}"
sections = ["User Problem", "Open Questions"]
interview = ["User journeys"]
upstream = { kind = "vision-doc", gate = "approved", map = { "Problem Statement" = "User Problem", "Open Questions" = "Open Questions" } }
"""


def write_catalog(root: Path, text: str) -> Path:
    path = root / "documents.toml"
    path.write_text(text, encoding="utf-8")
    return path


def loaded(path: Path = documents_catalog.CONFIG) -> dict:
    match documents_catalog.load(path):
        case Ok(docs):
            return docs
        case Err(failure):
            raise AssertionError(failure.message)


def test_the_shipped_catalog_loads_with_both_documents_in_order() -> None:
    docs = loaded()

    assert set(docs) == {"vision-doc", "prd"}
    assert docs["vision-doc"].sections == VISION_SECTIONS
    assert docs["vision-doc"].interview == VISION_INTERVIEW
    assert docs["vision-doc"].upstream is None
    assert docs["prd"].sections == PRD_SECTIONS
    assert docs["prd"].upstream is not None
    assert docs["prd"].upstream.kind == "vision-doc"
    assert docs["prd"].upstream.gate == "approved"


def test_the_prd_maps_vision_doc_sections_by_meaning() -> None:
    upstream = loaded()["prd"].upstream

    assert upstream is not None
    assert upstream.map == {
        "Problem Statement": "User Problem",
        "Target Users": "Personas",
        "Business Objectives": "Business Goals",
        "Success Metrics": "KPIs",
        "Constraints": "NFRs",
        "Out of Scope": "Out of Scope",
        "Open Questions": "Open Questions",
    }


def test_a_base_catalog_loads(tmp_path: Path) -> None:
    assert isinstance(documents_catalog.load(write_catalog(tmp_path, BASE)), Ok)


def test_a_mapping_to_a_section_the_document_lacks_is_refused(tmp_path: Path) -> None:
    text = BASE.replace(
        '"Problem Statement" = "User Problem"', '"Problem Statement" = "Nowhere"'
    )

    result = documents_catalog.load(write_catalog(tmp_path, text))

    assert isinstance(result, Err)
    assert "Nowhere" in result.failure.message


def test_a_mapping_from_a_section_the_upstream_lacks_is_refused(tmp_path: Path) -> None:
    text = BASE.replace(
        '"Problem Statement" = "User Problem"', '"Nowhere" = "User Problem"'
    )

    result = documents_catalog.load(write_catalog(tmp_path, text))

    assert isinstance(result, Err)
    assert "Nowhere" in result.failure.message


def test_an_upstream_kind_outside_the_catalog_is_refused(tmp_path: Path) -> None:
    text = BASE.replace('kind = "vision-doc"', 'kind = "charter"')

    result = documents_catalog.load(write_catalog(tmp_path, text))

    assert isinstance(result, Err)
    assert "charter" in result.failure.message


def test_status_labels_each_kind_of_section() -> None:
    prd = loaded()["prd"]
    content = (
        "# PRD — Acme\n\n"
        "## User Problem\n\nUsers lose their place between sessions.\n\n"
        "## Personas\n\nTBD\n\n"
        "## Business Goals\n\nTBD — waiting on finance (owner: Ana)\n\n"
        "## Out of Scope\n\n"
        "## Dependencies\n\nTBD - waiting on vendor (owner: Ben)\n"
    )

    states = documents_catalog.status(prd, content)

    assert states["User Problem"] == "complete"
    assert states["Personas"] == "placeholder"
    assert states["Business Goals"] == "complete"
    assert states["Out of Scope"] == "placeholder"
    assert states["Dependencies"] == "complete"
    assert states["Risks"] == "missing"


def test_approved_reads_the_status_line_under_the_title() -> None:
    assert documents_catalog.approved(
        "# PRD — Acme\n\nStatus: Approved\n\n## User Problem\n"
    )
    assert not documents_catalog.approved(
        "# PRD — Acme\n\nStatus: Draft\n\n## User Problem\n"
    )
    assert not documents_catalog.approved(
        "# PRD — Acme\n\n## User Problem\n\nStatus: Approved\n"
    )


DRAFT = """# PRD — Acme

Status: Draft

## User Problem

Users cannot find their orders.

## Change history

| Date | Change | By |
|---|---|---|
| 2026-11-11 | Draft | Ana |
"""


def test_substance_is_a_document_without_its_status_line_and_change_history() -> None:
    approved = DRAFT.replace("Status: Draft", "Status: Approved") + (
        "| 2026-11-12 | Approved by Ana | Ana |\n"
    )

    assert documents_catalog.substance(approved) == documents_catalog.substance(DRAFT)
    assert "Users cannot find their orders." in documents_catalog.substance(DRAFT)
    assert "Status" not in documents_catalog.substance(DRAFT)
    assert "Change history" not in documents_catalog.substance(DRAFT)


def test_substance_changes_with_any_other_word_or_section() -> None:
    reworded = DRAFT.replace("cannot find", "can find")
    extra_section = DRAFT.replace(
        "## Change history", "## Risks\n\nNone.\n\n## Change history"
    )

    assert documents_catalog.substance(reworded) != documents_catalog.substance(DRAFT)
    assert documents_catalog.substance(extra_section) != documents_catalog.substance(
        DRAFT
    )


def test_substance_ignores_trailing_blanks_and_a_status_line_only_under_the_title() -> (
    None
):
    spaced = DRAFT.replace("orders.", "orders.   ") + "\n\n"
    in_a_section = DRAFT.replace(
        "Users cannot find their orders.", "Status: Approved by finance"
    )

    assert documents_catalog.substance(spaced) == documents_catalog.substance(DRAFT)
    assert "Status: Approved by finance" in documents_catalog.substance(in_a_section)
