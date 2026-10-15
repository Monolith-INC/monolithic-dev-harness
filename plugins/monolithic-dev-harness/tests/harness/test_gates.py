"""Every standard question is ready in every language and passes the plain-wording check."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import gates, preferences, questions
from tests.harness.test_decisions import CLI
from tests.settings_fixture import write_settings

LANGUAGES, CATALOG = gates.load().value


def sample_values(gate: gates.Gate) -> dict[str, str]:
    return {slot: "3" for slot in gates._slots(gate, LANGUAGES[0])}


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("gate_id", sorted(CATALOG))
def test_every_gate_reads_plainly_in_every_language(
    gate_id: str, language: str
) -> None:
    rendered = gates.render(gate_id, language, sample_values(CATALOG[gate_id])).value
    assert not questions.problems(
        {
            "questions": [
                {
                    "question": rendered.question,
                    "header": "Review",
                    "options": [
                        {"label": label, "description": detail}
                        for label, detail in zip(
                            rendered.options, rendered.details, strict=True
                        )
                    ],
                }
            ]
        }
    )


def test_an_approval_gate_offers_approve_in_every_language() -> None:
    for gate in CATALOG.values():
        for language in LANGUAGES if gate.approval else ():
            labels = {option.label[language].casefold() for option in gate.options}
            assert labels & questions.APPROVE_LABELS, (gate.id, language)


def test_a_missing_translation_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "gates.toml"
    broken.write_text(
        'languages = ["en", "pt-br"]\n[[gate]]\nid = "x"\nquestion.en = "Go on?"\n'
        '[[gate.option]]\nid = "yes"\nlabel.en = "Yes"\ndetail.en = "Continue."\n'
    )
    assert isinstance(gates.load(broken), Err)


def test_slots_must_all_be_filled() -> None:
    assert isinstance(gates.render("publish-items", "en", {"count": "3"}), Err)
    assert isinstance(
        gates.render("publish-items", "en", {"count": "3", "tracker": "{x}"}), Err
    )
    assert isinstance(
        gates.render("publish-items", "en", {"count": "3", "tracker": "Linear"}), Ok
    )


def test_the_project_language_picks_the_wording(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    assert isinstance(preferences.set_language("pt-br", tmp_path), Ok)
    (tmp_path / "plan.md").write_text("plano")
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            str(tmp_path),
            "--gate",
            "plan-checkpoint",
            "--artifact",
            "plan.md",
            "--recommended",
            "deepen",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    menu = json.loads(result.stdout)["menu"].splitlines()
    assert menu[0] == "**O plano está pronto. Como você quer seguir?**"
    assert menu[3].startswith("2. **Aprofundar (Recomendado)**")


def test_a_gate_brings_its_own_wording() -> None:
    result = subprocess.run(
        [
            str(CLI),
            "decision",
            "present",
            "--repo",
            ".",
            "--gate",
            "next-step",
            "--question",
            "Something else?",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2 and "supplies its own question" in result.stderr


def test_refinement_asks_for_the_split_before_drafting_anything() -> None:
    split = CATALOG["refinement-split"]
    assert (split.kind, split.approval, split.artifact) == ("required", False, True)
    assert [option.id for option in split.options] == ["approve", "revise", "stop"]


def test_the_plan_approval_names_one_story() -> None:
    confirm = CATALOG["implementation-confirm"]
    assert gates._slots(confirm, "en") == {"story"}
    assert (confirm.approval, confirm.artifact, confirm.binds) == (
        True,
        True,
        "artifacts",
    )
    rendered = gates.render("implementation-confirm", "en", {"story": "DAY-1"}).value
    assert "DAY-1" in rendered.question
    assert isinstance(gates.render("implementation-confirm", "en", {}), Err)


def test_a_created_document_is_approved_before_it_is_saved() -> None:
    document = CATALOG["approve-document"]
    assert (document.approval, document.artifact, document.binds) == (
        True,
        True,
        "artifacts",
    )


@pytest.mark.parametrize(
    ("gate_id", "options"),
    [
        ("refined-start", ["investigate", "deliver"]),
        ("idea-continue", ["continue", "stop"]),
    ],
)
def test_route_choices_are_required_answers_without_writes(
    gate_id: str, options: list[str]
) -> None:
    gate = CATALOG[gate_id]
    assert (gate.kind, gate.approval, gate.binds) == ("required", False, "")
    assert [option.id for option in gate.options] == options
