"""write-spec writes technical specs only: the Story's implementation plan comes from the backlog."""

from __future__ import annotations

from pathlib import Path

import pytest

import spec_runtime
from artifact_profiles.spec import SPEC_REQUIRED_HEADINGS, spec_profile

TEMPLATES = (
    Path(__file__).resolve().parents[2] / "skills/write-spec/references/templates"
)


def test_the_implementation_plan_is_not_a_spec_kind() -> None:
    assert "implementation-plan" not in spec_runtime.SPEC_KINDS
    assert "implementation-plan" not in SPEC_REQUIRED_HEADINGS
    assert not (TEMPLATES / "implementation-plan.md").exists()
    for kinds in spec_runtime.DEFAULT_KINDS_BY_SIGNAL.values():
        assert "implementation-plan" not in kinds


@pytest.mark.parametrize("signal", sorted(spec_runtime.DEFAULT_KINDS_BY_SIGNAL))
def test_every_default_kind_has_a_template_and_a_profile(signal: str) -> None:
    for kind in spec_runtime.kinds_for_signal(signal):
        assert (TEMPLATES / f"{kind}.md").is_file()
        assert spec_profile(kind).required_headings


def test_a_tech_spec_points_at_the_approved_plan_instead_of_restating_it() -> None:
    template = (TEMPLATES / "tech-spec.md").read_text(encoding="utf-8")
    assert "## Implementation Plan" not in template
    assert "approved implementation plan" in template
    assert "Implementation Plan" not in SPEC_REQUIRED_HEADINGS["tech-spec"]


def test_only_missing_kinds_are_written() -> None:
    plan = spec_runtime.plan_spec_generation(
        "STORY-1",
        required_kinds=("tech-spec", "adr"),
        existing_artifacts=("tech-spec",),
    )
    assert plan.missing_kinds == ("adr",)
