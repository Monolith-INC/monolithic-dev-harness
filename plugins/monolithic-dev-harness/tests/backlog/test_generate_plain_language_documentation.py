"""Structural self-tests for generate-plain-language-documentation skill."""

from __future__ import annotations

import unittest

from plain_language_helpers import (
    GLOSSARY_DOC_PATH,
    GLOSSARY_PATH,
    PLAIN_LANGUAGE_SKILL,
    REQUIRED_PHASES,
    REQUIRED_REFERENCE_FILES,
    glossary_lookup_pt,
    load_json,
    read_skill_text,
    validate_glossary_structure,
    validate_skill_manifest,
)


class TestPlainLanguageSkillFrontmatter(unittest.TestCase):
    def test_name_and_description_present(self) -> None:
        content = read_skill_text("generate-plain-language-documentation", "SKILL.md")
        frontmatter_end = content.find("---", 3)
        self.assertNotEqual(frontmatter_end, -1)
        frontmatter = content[3:frontmatter_end].strip()
        self.assertIn("name: generate-plain-language-documentation", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("plain language", frontmatter.lower())


class TestPlainLanguageSkillPhases(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_md = read_skill_text("generate-plain-language-documentation", "SKILL.md")

    def test_required_phases_documented(self) -> None:
        for phase in REQUIRED_PHASES:
            with self.subTest(phase=phase):
                self.assertIn(phase, self.skill_md)

    def test_phase_workflow_sections(self) -> None:
        self.assertIn("COLLECT INPUTS", self.skill_md)
        self.assertIn("INGEST", self.skill_md)
        self.assertIn("DRAFT", self.skill_md)
        self.assertIn("GLOSSARY VERIFICATION", self.skill_md)
        self.assertIn("SELF-REVIEW", self.skill_md)
        self.assertIn("GATE & DESTINATION", self.skill_md)


class TestPlainLanguageSkillReferences(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_md = read_skill_text("generate-plain-language-documentation", "SKILL.md")

    def test_reference_files_exist(self) -> None:
        refs_dir = PLAIN_LANGUAGE_SKILL / "references"
        for name in REQUIRED_REFERENCE_FILES:
            with self.subTest(reference=name):
                self.assertTrue((refs_dir / name).is_file(), f"missing references/{name}")

    def test_skill_md_links_required_references(self) -> None:
        for name in (
            "plain-language-principles.md",
            "glossary-usage.md",
            "output-formats.md",
            "integration-notes.md",
            "pipeline.md",
        ):
            with self.subTest(reference=name):
                self.assertIn(name, self.skill_md)

    def test_glossary_path_documented(self) -> None:
        self.assertIn(GLOSSARY_DOC_PATH, self.skill_md)
        self.assertNotIn("<artifacts>/assets/tech-glossary", self.skill_md)
        glossary_usage = read_skill_text(
            "generate-plain-language-documentation", "references", "glossary-usage.md"
        )
        self.assertIn(GLOSSARY_DOC_PATH, glossary_usage)
        pipeline = read_skill_text(
            "generate-plain-language-documentation", "references", "pipeline.md"
        )
        self.assertIn(GLOSSARY_DOC_PATH, pipeline)


class TestPlainLanguageSkillRules(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_md = read_skill_text("generate-plain-language-documentation", "SKILL.md")
        self.principles = read_skill_text(
            "generate-plain-language-documentation", "references", "plain-language-principles.md"
        )

    def test_plain_language_rules_referenced(self) -> None:
        self.assertIn("quality gate", self.principles.lower())
        self.assertIn("calque", self.skill_md.lower())
        self.assertIn("glossary", self.skill_md.lower())

    def test_pt_br_glossary_lookup_documented(self) -> None:
        self.assertIn("pt-br", self.skill_md.lower())
        self.assertIn("aliases", read_skill_text(
            "generate-plain-language-documentation", "references", "glossary-usage.md"
        ))

    def test_output_formats_include_work_item_prose(self) -> None:
        output_formats = read_skill_text(
            "generate-plain-language-documentation", "references", "output-formats.md"
        )
        self.assertIn("## Work-item prose", output_formats)
        self.assertIn("## Requisitos", output_formats)
        self.assertIn("## Critérios de Aceite", output_formats)

    def test_quality_gate_checklist_in_principles(self) -> None:
        self.assertIn("Quality gate", self.principles)
        self.assertIn("glossary-checked", self.principles.lower())


class TestPlainLanguageManifest(unittest.TestCase):
    def test_manifest_json_valid(self) -> None:
        manifest = load_json(PLAIN_LANGUAGE_SKILL / "manifest.json")
        errors = validate_skill_manifest(manifest, expected_name="generate-plain-language-documentation")
        self.assertEqual(errors, [], msg="; ".join(errors))

    def test_manifest_language_and_document_type_enums(self) -> None:
        manifest = load_json(PLAIN_LANGUAGE_SKILL / "manifest.json")
        props = manifest["input_schema"]["properties"]
        self.assertEqual(props["language"]["enum"], ["en", "pt-br"])
        self.assertEqual(
            props["document_type"]["enum"],
            ["general", "report", "guide", "work-item-prose"],
        )
        self.assertEqual(manifest["output_signature"]["required"], ["body", "language"])


class TestPlainLanguageEvals(unittest.TestCase):
    def test_evals_json_structure(self) -> None:
        evals = load_json(PLAIN_LANGUAGE_SKILL / "evals" / "evals.json")
        self.assertEqual(evals["skill_name"], "generate-plain-language-documentation")
        self.assertGreaterEqual(len(evals["evals"]), 3)
        for item in evals["evals"]:
            self.assertIn("prompt", item)
            self.assertIn("expected_output", item)


class TestGlossaryAsset(unittest.TestCase):
    def test_glossary_file_exists(self) -> None:
        self.assertTrue(GLOSSARY_PATH.is_file(), f"missing glossary at {GLOSSARY_PATH}")

    def test_glossary_json_structure(self) -> None:
        data = load_json(GLOSSARY_PATH)
        errors = validate_glossary_structure(data)
        self.assertEqual(errors, [], msg="; ".join(errors))

    def test_glossary_sample_lookups(self) -> None:
        data = load_json(GLOSSARY_PATH)
        self.assertEqual(glossary_lookup_pt(data, "array"), "vetor")
        self.assertEqual(glossary_lookup_pt(data, "IDE"), data["terms"]["ide"]["pt"])
        self.assertIsNone(glossary_lookup_pt(data, "not-a-real-term-xyz"))


if __name__ == "__main__":
    unittest.main()
