"""Bootstrap copies a checked settings file once, ignores state locally, and seeds knowledge."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.settings_fixture import MINIMAL

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = PLUGIN_ROOT / "scripts" / "harness" / "bootstrap.py"
EXAMPLE = PLUGIN_ROOT / "examples" / "settings.example.json"


class BootstrapTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "app"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".gitignore").write_text("node_modules/\n")

    def bootstrap(self, source: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(BOOTSTRAP),
                "--repo",
                str(self.repo),
                "--settings-from",
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def candidate(self, value: dict) -> Path:
        path = Path(self._tmp.name) / "candidate.json"
        path.write_text(json.dumps(value))
        return path

    def test_the_example_opts_a_repository_in_once(self) -> None:
        done = self.bootstrap(EXAMPLE)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            (self.repo / ".harness" / "settings.json").read_text(), EXAMPLE.read_text()
        )
        self.assertIn(
            ".harness/state/", (self.repo / ".git" / "info" / "exclude").read_text()
        )
        self.assertEqual((self.repo / ".gitignore").read_text(), "node_modules/\n")
        self.assertTrue((self.repo / ".harness" / "knowledge").is_dir())
        again = self.bootstrap(self.candidate(MINIMAL))
        self.assertIn("kept existing", again.stdout)
        self.assertEqual(
            (self.repo / ".harness" / "settings.json").read_text(), EXAMPLE.read_text()
        )

    def test_invalid_settings_or_an_unusable_tracker_stop_it(self) -> None:
        broken = self.bootstrap(
            self.candidate({**MINIMAL, "branch_template": "no-key"})
        )
        self.assertEqual(broken.returncode, 2)
        self.assertFalse((self.repo / ".harness" / "settings.json").exists())
        missing = self.bootstrap(
            self.candidate({**MINIMAL, "tracker": {"name": "azure-devops"}})
        )
        self.assertEqual(missing.returncode, 2)
        self.assertIn("organization", missing.stderr)

    def test_an_unusable_tracker_leaves_the_repository_ungoverned_but_state_ignored(
        self,
    ) -> None:
        missing = self.bootstrap(
            self.candidate({**MINIMAL, "tracker": {"name": "linear"}})
        )
        self.assertEqual(missing.returncode, 2)
        self.assertIn("team", missing.stderr)
        self.assertFalse((self.repo / ".harness" / "settings.json").exists())
        self.assertIn(
            ".harness/state/", (self.repo / ".git" / "info" / "exclude").read_text()
        )
