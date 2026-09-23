"""Everything the harness keeps in a repository lives under `.harness/` (ADR-0008)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.harness import layout
from scripts.integrations.config import config_path, load_config

INTEGRATIONS = {
    "schemaVersion": 1,
    "branchTemplate": "{category}/{key}-{slug}",
    "tracker": {
        "adapter": "local_tracker",
        "root": ".local-tracker",
        "connection": {
            "command": "python3",
            "args": ["x.py", "--root", ".local-tracker"],
        },
    },
    "scm": {"adapter": "github", "connection": {"command": "gh", "args": []}},
}


def _write(path: Path, content: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class MigrateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _old_layout(self) -> None:
        _write(
            self.repo / ".codex-workflows/integrations.json", json.dumps(INTEGRATIONS)
        )
        _write(
            self.repo / ".codex-workflows/active-stage",
            "merge-story-stack-into-feature",
        )
        _write(self.repo / ".monolithic-code-review/sources.json")
        _write(self.repo / ".monolithic-code-review/knowledge/identity.md", "# who")
        _write(self.repo / ".agile-backlog-toolkit/config.json")
        _write(self.repo / ".agile-backlog-toolkit/reports/r.txt", "report")
        _write(self.repo / ".agile-backlog-toolkit.install.json")
        _write(self.repo / ".local-tracker/backlog/EPIC-0001.json")
        _write(self.repo / ".agentic/workflow_prompts/.gitkeep", "")
        _write(self.repo / ".agentic/backups/amend-workitems/t/tree.json")

    def test_an_old_layout_moves_under_one_folder(self) -> None:
        self._old_layout()
        layout.migrate(self.repo)
        for path in (
            ".harness/integrations.json",
            ".harness/review/sources.json",
            ".harness/review/knowledge/identity.md",
            ".harness/backlog/config.json",
            ".harness/backlog/reports/r.txt",
            ".harness/backlog/install.json",
            ".harness/tracker/backlog/EPIC-0001.json",
            ".harness/state/backups/amend-workitems/t/tree.json",
        ):
            with self.subTest(path=path):
                self.assertTrue((self.repo / path).is_file())
        # Nothing of the old layout is left behind.
        self.assertEqual(sorted(p.name for p in self.repo.iterdir()), [".harness"])

    def test_the_local_tracker_follows_its_folder(self) -> None:
        self._old_layout()
        layout.migrate(self.repo)
        tracker = json.loads((self.repo / ".harness/integrations.json").read_text())[
            "tracker"
        ]
        self.assertEqual(tracker["root"], ".harness/tracker")
        self.assertEqual(tracker["connection"]["args"][-1], ".harness/tracker")

    def test_nothing_is_overwritten(self) -> None:
        _write(self.repo / ".codex-workflows/integrations.json", '{"old": true}')
        _write(self.repo / ".harness/integrations.json", '{"new": true}')
        notes = layout.migrate(self.repo)
        self.assertEqual(
            json.loads((self.repo / ".harness/integrations.json").read_text()),
            {"new": True},
        )
        self.assertTrue((self.repo / ".codex-workflows/integrations.json").exists())
        self.assertTrue(any("merge them by hand" in note for note in notes))

    def test_an_old_folder_holding_other_files_is_kept(self) -> None:
        _write(self.repo / ".codex-workflows/integrations.json")
        _write(self.repo / ".codex-workflows/notes.txt", "mine")
        notes = layout.migrate(self.repo)
        self.assertTrue((self.repo / ".codex-workflows/notes.txt").exists())
        self.assertTrue(any("still holds files" in note for note in notes))

    def test_a_current_layout_is_left_alone(self) -> None:
        _write(self.repo / ".harness/integrations.json")
        self.assertEqual(layout.migrate(self.repo), [])


class FallbackTests(unittest.TestCase):
    def test_an_unmigrated_repository_still_loads_its_integrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(
                repo / ".codex-workflows/integrations.json", json.dumps(INTEGRATIONS)
            )
            self.assertEqual(
                config_path(repo), repo / ".codex-workflows/integrations.json"
            )
            self.assertEqual(load_config(repo).tracker["adapter"], "local_tracker")

    def test_the_new_location_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(
                repo / ".codex-workflows/integrations.json", json.dumps(INTEGRATIONS)
            )
            _write(repo / ".harness/integrations.json", json.dumps(INTEGRATIONS))
            self.assertEqual(config_path(repo), repo / ".harness/integrations.json")


if __name__ == "__main__":
    unittest.main()
