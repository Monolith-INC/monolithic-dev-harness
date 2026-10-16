"""Each preparation document is shown and approved when created, then saved where the team sees it."""

from __future__ import annotations

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]


def test_each_document_is_approved_then_saved_and_published() -> None:
    contract = " ".join(
        (PLUGIN / "references/onboarding.md").read_text(encoding="utf-8").split()
    )
    preparation = contract.split("## Preparation", 1)[1].split("## ", 1)[0]
    assert preparation.index("--gate approve-document") < preparation.index(
        "tracker_publish_artifact"
    )
    assert "status: draft" in preparation
    assert "needs a new approval" in preparation
