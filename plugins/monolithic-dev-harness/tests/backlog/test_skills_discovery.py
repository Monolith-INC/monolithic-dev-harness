import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "skills"
EXPECTED = (
    "decompose-backlog",
    "validate-artifact",
    "auto-fix-artifact",
    "split-story",
    "generate-work-item",
    "enrich-work-item",
    "generate-plain-language-documentation",
    "generate-breakdown-work-items",
    "amend-workitems",
)
PORTABLE_FM = frozenset({"name", "description", "license"})


class TestSkillsDiscoveryLayout(unittest.TestCase):
    def test_root_skills_are_real_directories(self) -> None:
        self.assertTrue(SKILLS_ROOT.is_dir())
        for name in EXPECTED:
            skill = SKILLS_ROOT / name
            self.assertTrue(skill.is_dir(), f"skills/{name} must be a real directory")
            self.assertFalse(skill.is_symlink(), f"skills/{name} must not be a symlink")
            self.assertTrue((skill / "SKILL.md").is_file())

    def test_skill_frontmatter_is_portable_only(self) -> None:
        for name in EXPECTED:
            text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            end = text.find("\n---", 4)
            fm = text[4:end]
            keys = {
                line.split(":", 1)[0].strip()
                for line in fm.splitlines()
                if line.strip()
                and not line.startswith(" ")
                and not line.startswith("#")
                and ":" in line
            }
            self.assertEqual(keys, PORTABLE_FM, msg=f"{name} keys={keys}")

