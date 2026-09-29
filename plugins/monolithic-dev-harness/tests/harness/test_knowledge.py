"""The harness-owned knowledge store is immutable, local, and seeded from the settings file."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.harness import knowledge
from tests.settings_fixture import write_settings


def _settings(repo: Path, branch: str = "main") -> Path:
    return write_settings(repo, git={"base_branch": branch})


class KnowledgeStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _settings(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_initialize_creates_a_settings_seed_and_is_idempotent(self) -> None:
        created = knowledge.initialize(self.repo)
        unchanged = knowledge.initialize(self.repo)
        listed = knowledge.catalog(self.repo)
        self.assertEqual(created["outcome"], "created")
        self.assertEqual(unchanged["outcome"], "unchanged")
        self.assertEqual(
            [item["logical_unit_id"] for item in listed], ["project/harness-settings"]
        )
        self.assertEqual(knowledge.status(self.repo)["current"], 1)

    def test_refresh_keeps_the_old_revision_and_marks_it_stale(self) -> None:
        before = knowledge.initialize(self.repo)["revision"]
        _settings(self.repo, "develop")
        refreshed = knowledge.refresh(self.repo)
        after = refreshed["revision"]
        self.assertEqual(refreshed["outcome"], "refreshed")
        self.assertNotEqual(before, after)
        self.assertEqual(
            knowledge.fetch(self.repo, f"project/harness-settings@{before}")["status"],
            "superseded",
        )
        self.assertEqual(
            knowledge.fetch(self.repo, "project/harness-settings")["revision_id"], after
        )
        self.assertEqual(knowledge.status(self.repo)["stale"], 1)

    def test_find_is_bounded_and_fetches_only_the_current_revision(self) -> None:
        knowledge.initialize(self.repo)
        matches = knowledge.find(self.repo, ["generated", "workflow"])
        fetched = knowledge.fetch(self.repo, matches[0]["logical_unit_id"])
        self.assertEqual(len(matches), 1)
        self.assertEqual(fetched["status"], "current")
        self.assertEqual(fetched["provenance"]["confidence"], "source_backed")

    def test_store_ids_cannot_escape_the_harness_root(self) -> None:
        with self.assertRaises(knowledge.KnowledgeError):
            knowledge.initialize(self.repo, "../outside")


if __name__ == "__main__":
    unittest.main()
