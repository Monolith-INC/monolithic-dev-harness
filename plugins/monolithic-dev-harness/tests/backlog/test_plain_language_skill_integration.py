"""Integration tests: sibling skills wired to generate-plain-language-documentation."""

from __future__ import annotations

import unittest
from pathlib import Path

from plain_language_helpers import (
    INTEGRATION_NOTES_REL,
    missing_substrings,
    read_skill_text,
)

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "common"


class TestIntegrationNotesContract(unittest.TestCase):
    def setUp(self) -> None:
        self.notes = read_skill_text(
            "generate-plain-language-documentation", "references", "integration-notes.md"
        )

    def test_documents_all_sibling_hooks(self) -> None:
        for section in ("## generate-work-item", "## enrich-work-item", "## decompose-backlog"):
            with self.subTest(section=section):
                self.assertIn(section, self.notes)

    def test_sub_skill_mode_contract(self) -> None:
        self.assertIn("Sub-skill", self.notes)
        self.assertIn("PHASE 2–4", self.notes)

    def test_generate_work_item_hook_details(self) -> None:
        section = self._section_after("## generate-work-item")
        missing = missing_substrings(
            section,
            (
                "PHASE 4",
                "## Requisitos",
                "## Critérios de Aceite",
                "work-item-prose",
            ),
        )
        self.assertEqual(missing, [], msg=f"missing in generate-work-item section: {missing}")

    def test_enrich_work_item_hook_details(self) -> None:
        section = self._section_after("## enrich-work-item")
        missing = missing_substrings(
            section,
            (
                "PHASE 4",
                "Descrição Original",
                "emoji headings",
            ),
        )
        self.assertEqual(missing, [], msg=f"missing in enrich-work-item section: {missing}")

    def test_decompose_backlog_hook_details(self) -> None:
        section = self._section_after("## decompose-backlog")
        missing = missing_substrings(
            section,
            (
                "PHASE 3",
                "PHASE 4",
                "DRAFT",
                "ENRICH",
            ),
        )
        self.assertEqual(missing, [], msg=f"missing in decompose-backlog section: {missing}")

    def _section_after(self, heading: str) -> str:
        start = self.notes.index(heading)
        rest = self.notes[start + len(heading) :]
        next_heading = rest.find("\n## ")
        return rest if next_heading == -1 else rest[:next_heading]


class TestGenerateWorkItemIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_md = read_skill_text("generate-work-item", "SKILL.md")
        self.pipeline = (COMMON / "workflows" / "generate-work-item.md").read_text(encoding="utf-8")
        self.output_formats = (COMMON / "templates" / "output-formats.md").read_text(encoding="utf-8")

    def test_skill_references_integration_notes(self) -> None:
        self.assertIn(INTEGRATION_NOTES_REL, self.skill_md)

    def test_phase4_prose_sub_pass_before_present(self) -> None:
        missing = missing_substrings(
            self.skill_md,
            (
                "PHASE 4",
                "Requisitos",
                "Critérios de Aceite",
                "generate-plain-language-documentation",
                "work-item-prose",
            ),
        )
        self.assertEqual(missing, [], msg=f"missing hooks: {missing}")

    def test_pipeline_and_output_formats_reference_plain_language(self) -> None:
        self.assertIn("generate-plain-language-documentation", self.pipeline)
        # common/workflows/ sits two levels below the plugin root, so its link differs from the skill's.
        self.assertIn("../../skills/generate-plain-language-documentation/references/integration-notes.md", self.pipeline)
        self.assertIn("generate-plain-language-documentation", self.output_formats)
        self.assertIn("work-item-prose", self.output_formats)


class TestEnrichWorkItemIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_md = read_skill_text("enrich-work-item", "SKILL.md")
        self.pipeline = (COMMON / "workflows" / "enrich-work-item.md").read_text(encoding="utf-8")

    def test_skill_references_integration_notes(self) -> None:
        self.assertIn(INTEGRATION_NOTES_REL, self.skill_md)

    def test_phase4_prose_sub_pass_after_enricher(self) -> None:
        phase4_start = self.skill_md.index("## PHASE 4")
        phase4 = self.skill_md[phase4_start:]
        missing = missing_substrings(
            phase4,
            (
                "generate-plain-language-documentation",
                "narrative paragraphs",
                "emoji headings",
                "Descrição Original",
            ),
        )
        self.assertEqual(missing, [], msg=f"missing hooks: {missing}")

    def test_pipeline_lists_plain_language_skill(self) -> None:
        self.assertIn("generate-plain-language-documentation", self.pipeline)

    def test_no_external_asset_override(self) -> None:
        self.assertNotIn("<artifacts>/assets/", self.skill_md)
        self.assertNotIn("prefer when present", self.skill_md.lower())
        self.assertIn("../../common/workflows/enrichers/", self.skill_md)


class TestDecomposeBacklogIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_md = read_skill_text("decompose-backlog", "SKILL.md")

    def test_skill_references_integration_notes(self) -> None:
        self.assertIn(INTEGRATION_NOTES_REL, self.skill_md)

    def test_draft_and_enrich_prose_sub_passes(self) -> None:
        missing = missing_substrings(
            self.skill_md,
            (
                "generate-plain-language-documentation",
                "DRAFT",
                "ENRICH",
                "scope lines",
            ),
        )
        self.assertEqual(missing, [], msg=f"missing hooks: {missing}")

    def test_integration_notes_cited_in_draft_and_enrich_sections(self) -> None:
        draft_start = self.skill_md.index("### 3. DRAFT")
        enrich_start = self.skill_md.index("### 4. ENRICH")
        draft_section = self.skill_md[draft_start:enrich_start]
        enrich_section = self.skill_md[enrich_start:]
        self.assertIn(INTEGRATION_NOTES_REL, draft_section)
        self.assertIn(INTEGRATION_NOTES_REL, enrich_section)
        self.assertIn("generate-plain-language-documentation", draft_section)
        self.assertIn("generate-plain-language-documentation", enrich_section)


if __name__ == "__main__":
    unittest.main()
