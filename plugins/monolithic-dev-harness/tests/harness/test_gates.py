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
