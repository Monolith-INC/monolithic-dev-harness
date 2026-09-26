import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from orchestrator_core.artifact_validator import (
    critiques_from_results,
    outcome_from_results,
    validate_artifact,
)
from orchestrator_core.engine import OrchestratorEngine
from orchestrator_core.ingest import ingest_file, ingest_from_text
from orchestrator_core.reflection import (
    ReflectionState,
    advance_reflection,
    evaluate_reflection,
)

FIXTURE = Path(__file__).resolve().parents[2] / (
    "tests/backlog/fixtures/6869-login-form-validation.md"
)

RAW_GENERATE_STORY = """\
---
date: 2026-07-08
type: ticket
work_item_type: User Story
provider: filesystem
provider_id: local-6869
parent_id: 6868
tags: [ticket, user-story]
---

# Validação de campos do formulário de login

[[Specs/6869-login-form-validation-spec]]

## Requisitos

- Validar formato de e-mail ao sair do campo
- Validar senha não vazia no envio

## Critérios de Aceite

- [ ] Exibir erro quando e-mail estiver vazio
- [ ] Exibir erro quando senha estiver vazia
"""


EN_STORY_BODY = """\
# Validate login form fields and show inline errors

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


class TestArtifactValidator(unittest.TestCase):
    def test_good_story_passes(self) -> None:
        record = ingest_file(FIXTURE)
        results = validate_artifact(record)
        self.assertEqual(outcome_from_results(results), "PASS")

    def test_raw_generate_story_passes(self) -> None:
        record = ingest_from_text(
            RAW_GENERATE_STORY, filename="6869-login-form-validation"
        )
        results = validate_artifact(record)
        self.assertEqual(outcome_from_results(results), "PASS")
        names = [r.name for r in results if r.result == "FAIL"]
        self.assertNotIn("body-section-missing: 🎯 O quê", names)

    def _hierarchy(self, results):
        return next(r for r in results if r.name == "hierarchy-story-parent-is-feature")

    def test_story_without_parent_passes(self) -> None:
        text = RAW_GENERATE_STORY.replace("parent_id: 6868\n", "")
        record = ingest_from_text(text, filename="draft-login-form-validation")
        self.assertIsNone(record.parent_id)
        results = validate_artifact(record)
        self.assertEqual(outcome_from_results(results), "PASS")
        self.assertEqual(self._hierarchy(results).result, "PASS")
        self.assertNotIn("dor-linked-to-feature", [r.name for r in results])

    def test_story_under_non_feature_parent_fails(self) -> None:
        record = ingest_from_text(
            RAW_GENERATE_STORY, filename="6869-login-form-validation"
        )
        results = validate_artifact(record, hierarchy_parent_is_feature=False)
        self.assertEqual(outcome_from_results(results), "FAIL")
        self.assertEqual(self._hierarchy(results).result, "FAIL")

    def test_story_with_unverified_parent_is_skipped(self) -> None:
        record = ingest_from_text(
            RAW_GENERATE_STORY, filename="6869-login-form-validation"
        )
        self.assertEqual(self._hierarchy(validate_artifact(record)).result, "SKIP")

    def test_missing_type_fails(self) -> None:
        record = ingest_file(FIXTURE)
        bad = replace(record, frontmatter={})
        results = validate_artifact(bad)
        self.assertEqual(outcome_from_results(results), "FAIL")
        names = [r.name for r in results if r.result == "FAIL"]
        self.assertIn("frontmatter-type-present", names)

    def test_pt_br_story_defaults_when_language_key_absent(self) -> None:
        record = ingest_file(FIXTURE)
        self.assertNotIn("language", record.frontmatter)
        results = validate_artifact(record)
        self.assertEqual(outcome_from_results(results), "PASS")

    def test_en_story_fails_without_language_frontmatter(self) -> None:
        record = ingest_from_text(
            "---\ntype: ticket\nwork_item_type: User Story\nstory_points: 2\n---\n\n"
            + EN_STORY_BODY,
            filename="0000-en-story",
        )
        results = validate_artifact(record)
        self.assertEqual(outcome_from_results(results), "FAIL")
        names = [r.name for r in results if r.result == "FAIL"]
        # Default language is pt-BR; EN headings route as enriched_story and fail format checks.
        self.assertTrue(
            any(
                name.startswith("body-section-missing: 🎯")
                or name == "body-enriched-story-format"
                for name in names
            )
        )

    def test_en_story_passes_with_language_en_frontmatter(self) -> None:
        record = ingest_from_text(
            "---\ntype: ticket\nwork_item_type: User Story\nstory_points: 2\nlanguage: en\n---\n\n"
            + EN_STORY_BODY,
            filename="0000-en-story",
        )
        results = validate_artifact(record)
        self.assertEqual(outcome_from_results(results), "PASS")

    def test_pt_br_story_fails_when_declared_language_is_en(self) -> None:
        record = ingest_file(FIXTURE)
        mislabeled = replace(
            record, frontmatter={**record.frontmatter, "language": "en"}
        )
        results = validate_artifact(mislabeled)
        self.assertEqual(outcome_from_results(results), "FAIL")

    def test_warn_only_outcome_is_pass(self) -> None:
        record = ingest_file(FIXTURE)
        warned = replace(record, body=f"{record.body}\nRef: /home/user/projects/repo\n")
        results = validate_artifact(warned)
        self.assertEqual(outcome_from_results(results), "PASS")
        self.assertTrue(
            any(
                "content-no-machine-paths" in c for c in critiques_from_results(results)
            )
        )


class TestOrchestratorEngine(unittest.TestCase):
    def test_validate_artifact_warn_only_completes(self) -> None:
        skills_dir = Path(__file__).resolve().parents[2] / "skills"
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_dir = project_root / ".harness" / "backlog"
            state_dir.mkdir(parents=True)
            engine = OrchestratorEngine(
                skills_dir=skills_dir,
                project_root=project_root,
                state_dir=state_dir,
                quiet=True,
            )
            result = engine.run_tool_call(
                "validate-artifact",
                {"file_path": str(FIXTURE)},
            )
            self.assertTrue(result.ok, result.error)

    def test_evaluate_file_warn_only_passes(self) -> None:
        skills_dir = Path(__file__).resolve().parents[2] / "skills"
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            state_dir = project_root / ".harness" / "backlog"
            state_dir.mkdir(parents=True)
            engine = OrchestratorEngine(
                skills_dir=skills_dir,
                project_root=project_root,
                state_dir=state_dir,
                quiet=True,
            )
            ok, _report = engine.evaluate_file(FIXTURE)
            self.assertTrue(ok)


class TestReflection(unittest.TestCase):
    def test_circuit_breaker_on_max_attempts(self) -> None:
        state = ReflectionState()
        for _ in range(3):
            state = advance_reflection(state, ["missing section"], max_attempts=3)
        self.assertTrue(state.blocked)

    def test_identical_critiques_trip_breaker(self) -> None:
        state = advance_reflection(ReflectionState(), ["same"], max_attempts=3)
        state = advance_reflection(state, ["same"], max_attempts=3)
        self.assertTrue(state.blocked)

    def test_clean_pass_completed_mode(self) -> None:
        decision = evaluate_reflection([], has_draft=True)
        self.assertEqual(decision.mode, "completed")


if __name__ == "__main__":
    unittest.main()
