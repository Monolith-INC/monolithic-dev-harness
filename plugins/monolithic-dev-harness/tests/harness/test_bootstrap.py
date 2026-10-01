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
        exclude = (self.repo / ".git" / "info" / "exclude").read_text()
        self.assertIn(".harness/state/", exclude)
        self.assertIn(".harness/tracker/", exclude)
        self.assertEqual((self.repo / ".gitignore").read_text(), "node_modules/\n")
        self.assertTrue((self.repo / ".harness" / "knowledge").is_dir())
        codex_config = self.repo / ".codex" / "config.toml"
        self.assertIn("[features]", codex_config.read_text())
        self.assertIn("default_mode_request_user_input = true", codex_config.read_text())
        again = self.bootstrap(self.candidate(MINIMAL))
        self.assertIn("kept existing", again.stdout)
        self.assertEqual(
            (self.repo / ".harness" / "settings.json").read_text(), EXAMPLE.read_text()
        )
        self.assertEqual((self.repo / ".git" / "info" / "exclude").read_text(), exclude)

    def test_existing_codex_config_is_extended_without_losing_other_settings(self) -> None:
        config = self.repo / ".codex" / "config.toml"
        config.parent.mkdir()
        config.write_text("[features]\nother_feature = true\n\n[projects]\nname = 'app'\n")
        done = self.bootstrap(EXAMPLE)
        self.assertEqual(done.returncode, 0, done.stderr)
        content = config.read_text()
        self.assertIn("other_feature = true", content)
        self.assertIn("default_mode_request_user_input = true", content)
        self.assertIn("[projects]\nname = 'app'", content)
        self.assertLess(content.index("default_mode_request_user_input"), content.index("[projects]"))

    def test_disabled_codex_picker_is_not_overwritten(self) -> None:
        config = self.repo / ".codex" / "config.toml"
        config.parent.mkdir()
        original = "[features]\ndefault_mode_request_user_input = false\n"
        config.write_text(original)
        done = self.bootstrap(EXAMPLE)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("explicitly disables default_mode_request_user_input", done.stderr)
        self.assertEqual(config.read_text(), original)

    def test_an_existing_state_ignore_gains_the_local_tracker(self) -> None:
        exclude = self.repo / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("*.log\n.harness/state/\n")
        done = self.bootstrap(EXAMPLE)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            exclude.read_text(), "*.log\n.harness/state/\n.harness/tracker/\n"
        )

    def test_committed_tracker_records_get_a_warning(self) -> None:
        folder = self.repo / ".harness" / "tracker" / "backlog"
        folder.mkdir(parents=True)
        (folder / "STORY-0001.json").write_text("{}")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        done = self.bootstrap(EXAMPLE)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("git rm -r --cached --ignore-unmatch", done.stderr)

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
