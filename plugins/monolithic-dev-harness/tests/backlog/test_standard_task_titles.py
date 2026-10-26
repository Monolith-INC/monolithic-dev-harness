import unittest

from orchestrator_core.artifact_validator import validate_artifact
from orchestrator_core.ingest import ingest_from_text


def _title_check(kind: str, title: str):
    record = ingest_from_text(
        f"---\ntype: ticket\nwork_item_type: {kind}\nlanguage: en\n---\n\n# {title}\n\nBody.\n"
    )
    return next(c for c in validate_artifact(record) if c.name == "dor-title-clear")


class TestStandardTaskTitles(unittest.TestCase):
    """The breakdown's default Tasks pass the title check that other items must meet."""

    def test_default_task_titles_pass(self):
        for title in ("Staging", "Review", "Breakdown"):
            with self.subTest(title=title):
                self.assertEqual(_title_check("Task", title).result, "PASS")

    def test_other_short_titles_still_fail(self):
        self.assertEqual(_title_check("Task", "Counting rule").result, "FAIL")
        self.assertEqual(_title_check("User Story", "Review").result, "FAIL")


if __name__ == "__main__":
    unittest.main()
