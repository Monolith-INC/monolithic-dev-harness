"""Structural compliance tests for Agile Backlog Toolkit output formats."""

from __future__ import annotations

import unittest
from pathlib import Path

from orchestrator_core.output_formats import (
    validate_enrich_epic_body,
    validate_enrich_feature_body,
    validate_enrich_user_story_body,
    validate_generate_work_item_body,
    validate_split_story_spike_body,
    validate_ticket_structure_body,
    validate_validation_report_body,
)

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
COMMON = ROOT / "common"
COMMON_TEMPLATES = COMMON / "templates"
COMMON_CONTRACTS = COMMON / "contracts"


def _read_template(name: str) -> str:
    return (COMMON_TEMPLATES / name).read_text(encoding="utf-8")


def _read_unique_contract(skill: str, name: str) -> str:
    return (COMMON_CONTRACTS / skill / name).read_text(encoding="utf-8")


def _read_example(skill: str, name: str) -> str:
    return (SKILLS / skill / "references" / "examples" / name).read_text(encoding="utf-8")


COMPLIANT_GENERATE = """\
# Login field validation

[[Specs/6868-login-field-validation-spec]]

## Requisitos

- Validate email format on blur
- Validate password is non-empty on submit

## Critérios de Aceite

- [ ] Exibir erro quando e-mail estiver vazio
- [ ] Exibir erro quando senha estiver vazia
"""

COMPLIANT_ENRICH_EPIC = _read_example("enrich-work-item", "example-epic.md")
COMPLIANT_ENRICH_FEATURE = _read_example("enrich-work-item", "example-feature.md")
COMPLIANT_ENRICH_USER_STORY = _read_example("enrich-work-item", "example-user-story.md")

COMPLIANT_TICKET_STRUCTURE = """\
## 🎯 O quê

Validar campos de login com mensagens inline.

## 💡 Por quê

Usuários não recebem feedback ao submeter formulários inválidos.

## 📋 Comportamento esperado

- Exibir erro ao sair do campo vazio

## ✅ Critérios de Aceite

- [ ] Exibir mensagem quando e-mail estiver vazio
- [ ] Exibir mensagem quando senha estiver vazia

## 🔧 Notas Técnicas

- Módulo de autenticação

## 📊 Complexidade

**2 pontos** — Maior driver: Escopo=2, Incerteza=1, Integrações=1, Dados=1, QA=2, Rollout=1 → 2 pontos

## 📄 Descrição Original

História fictícia para validação de login.
"""

COMPLIANT_TICKET_STRUCTURE_EN = """\
## 🎯 What

Validate login fields with inline error messages.

## 💡 Why

Users get no feedback when submitting invalid forms.

## 📋 Expected Behavior

- Show an error when leaving an empty field

## ✅ Acceptance Criteria

- [ ] Show a message when the email field is empty
- [ ] Show a message when the password field is empty

## 🔧 Technical Notes

- Authentication module

## 📊 Complexity

**2 points** — Largest driver: Scope=2, Uncertainty=1, Integrations=1, Data=1, QA=2, Rollout=1 → 2 points

## 📄 Original Description

Fictional story for login validation.
"""

COMPLIANT_SPIKE = """\
**🎯 O quê**

Investigar abordagem para cache distribuído antes de implementar a história original.

**💡 Por quê**

Incerteza técnica impede estimativa confiável.

**📋 Comportamento esperado**

Ao final do spike, a equipe tem: documento com abordagem recomendada e nova estimativa.

**✅ Critérios de Aceite**

- [ ] Documentar pelo menos duas opções avaliadas
- [ ] Registrar recomendação com trade-offs

Time-box: 2 dias.

**📊 Complexidade**

3 pts — driver: Escopo=3 (spike output = decision doc + re-estimate); Incerteza=1 (investigation itself is bounded).

**📄 Descrição Original**

Precisamos cache distribuído mas não sabemos qual tecnologia usar.
"""

COMPLIANT_REPORT = _read_unique_contract("validate-artifact", "canonical-validation-report.md").replace(
    "{{ARTIFACT_TYPE}}", "User Story"
).replace("{{TITLE}}", "Login field validation").replace("{{SOURCE}}", "file").replace(
    "{{PASSED}}", "12"
).replace("{{FAILED}}", "0").replace("{{WARNINGS}}", "0").replace("{{OUTCOME}}", "PASS")


class TestGenerateWorkItemFormat(unittest.TestCase):
    def test_canonical_templates_pass(self) -> None:
        for name in ("canonical-epic.md", "canonical-feature.md", "canonical-user-story.md", "canonical-task.md"):
            self.assertTrue(_read_template(name).strip(), msg=name)

    def test_compliant_synthetic_passes(self) -> None:
        result = validate_generate_work_item_body(COMPLIANT_GENERATE)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_missing_requisitos_fails(self) -> None:
        body = COMPLIANT_GENERATE.replace("## Requisitos\n\n", "")
        result = validate_generate_work_item_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("Requisitos" in e for e in result.errors))

    def test_wrong_section_order_fails(self) -> None:
        body = COMPLIANT_GENERATE.replace(
            "## Requisitos\n\n- Validate email format on blur\n- Validate password is non-empty on submit\n\n## Critérios de Aceite",
            "## Critérios de Aceite\n\n- [ ] Exibir erro\n\n## Requisitos\n\n- Validate email",
        )
        result = validate_generate_work_item_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("order" in e for e in result.errors))

    def test_forbidden_enricher_section_fails(self) -> None:
        body = COMPLIANT_GENERATE + "\n## 🎯 O quê\n\nShould not appear.\n"
        result = validate_generate_work_item_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("forbidden" in e for e in result.errors))

    def test_missing_spec_wikilink_fails(self) -> None:
        body = COMPLIANT_GENERATE.replace("[[Specs/6868-login-field-validation-spec]]\n\n", "")
        result = validate_generate_work_item_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("wikilink" in e for e in result.errors))


class TestEnrichWorkItemFormat(unittest.TestCase):
    def test_canonical_epic_passes(self) -> None:
        result = validate_enrich_epic_body(_read_template("canonical-epic.md"))
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_canonical_feature_passes(self) -> None:
        result = validate_enrich_feature_body(
            _read_template("canonical-feature.md")
        )
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_canonical_user_story_passes(self) -> None:
        result = validate_enrich_user_story_body(
            _read_template("canonical-user-story.md")
        )
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_example_epic_passes(self) -> None:
        self.assertTrue(validate_enrich_epic_body(COMPLIANT_ENRICH_EPIC).ok)

    def test_example_feature_passes(self) -> None:
        self.assertTrue(validate_enrich_feature_body(COMPLIANT_ENRICH_FEATURE).ok)

    def test_example_user_story_passes(self) -> None:
        self.assertTrue(validate_enrich_user_story_body(COMPLIANT_ENRICH_USER_STORY).ok)

    def test_epic_missing_section_fails(self) -> None:
        body = COMPLIANT_ENRICH_EPIC.replace("## 📄 Descrição Original\n", "")
        result = validate_enrich_epic_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("Descrição Original" in e for e in result.errors))

    def test_feature_wrong_order_fails(self) -> None:
        body = COMPLIANT_ENRICH_FEATURE.replace(
            "## 🎯 Objetivo",
            "## 📦 Escopo\n\n### Incluído\n- x\n\n### Excluído (Fora do Escopo)\n- y\n\n## 🎯 Objetivo",
        ).replace("## 📦 Escopo\n\n### Incluído\n- Formulário", "## REMOVED\n\n### Incluído\n- Formulário", 1)
        result = validate_enrich_feature_body(body)
        self.assertFalse(result.ok)


class TestTicketStructureFormat(unittest.TestCase):
    def test_decompose_canonical_passes(self) -> None:
        body = _read_template("canonical-user-story.md")
        self.assertTrue(validate_ticket_structure_body(body).ok)

    def test_split_story_canonical_passes(self) -> None:
        body = _read_template("canonical-user-story.md")
        self.assertTrue(validate_ticket_structure_body(body).ok)

    def test_decompose_canonical_en_passes(self) -> None:
        body = _read_unique_contract("decompose-backlog", "canonical-user-story.en.md")
        result = validate_ticket_structure_body(body, language="en")
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_compliant_synthetic_passes(self) -> None:
        self.assertTrue(validate_ticket_structure_body(COMPLIANT_TICKET_STRUCTURE).ok)

    def test_missing_complexidade_fails(self) -> None:
        body = COMPLIANT_TICKET_STRUCTURE.replace("## 📊 Complexidade\n\n**2 pontos**", "")
        result = validate_ticket_structure_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("Complexidade" in e for e in result.errors))

    def test_pt_br_body_fails_when_language_en_requested(self) -> None:
        result = validate_ticket_structure_body(COMPLIANT_TICKET_STRUCTURE, language="en")
        self.assertFalse(result.ok)

    def test_en_compliant_passes_with_language_en(self) -> None:
        result = validate_ticket_structure_body(COMPLIANT_TICKET_STRUCTURE_EN, language="en")
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_en_body_fails_under_default_pt_br_language(self) -> None:
        result = validate_ticket_structure_body(COMPLIANT_TICKET_STRUCTURE_EN)
        self.assertFalse(result.ok)

    def test_unknown_language_falls_back_to_pt_br(self) -> None:
        result = validate_ticket_structure_body(COMPLIANT_TICKET_STRUCTURE, language="fr")
        self.assertTrue(result.ok, msg=str(result.errors))


class TestSplitStorySpikeFormat(unittest.TestCase):
    def test_canonical_spike_passes(self) -> None:
        body = _read_unique_contract("split-story", "canonical-spike.md")
        self.assertTrue(validate_split_story_spike_body(body).ok)

    def test_compliant_synthetic_passes(self) -> None:
        self.assertTrue(validate_split_story_spike_body(COMPLIANT_SPIKE).ok)

    def test_missing_bold_section_fails(self) -> None:
        body = COMPLIANT_SPIKE.replace("**📄 Descrição Original**\n\n", "")
        result = validate_split_story_spike_body(body)
        self.assertFalse(result.ok)


class TestValidationReportFormat(unittest.TestCase):
    def test_canonical_report_passes(self) -> None:
        self.assertTrue(validate_validation_report_body(COMPLIANT_REPORT).ok)

    def test_missing_outcome_fails(self) -> None:
        body = COMPLIANT_REPORT.replace("Outcome: PASS\n", "")
        result = validate_validation_report_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("Outcome" in e for e in result.errors))

    def test_missing_category_fails(self) -> None:
        body = COMPLIANT_REPORT.replace("HIERARCHY\n", "")
        result = validate_validation_report_body(body)
        self.assertFalse(result.ok)
        self.assertTrue(any("HIERARCHY" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
