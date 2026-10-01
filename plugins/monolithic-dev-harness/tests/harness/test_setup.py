"""Assisted setup proposes exact changes and preserves existing settings."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.result import Err, Ok
from scripts.harness import settings, setup

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CLI = PLUGIN_ROOT / "scripts/harness/cli.py"


class SetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.preference_env = {
            "HARNESS_USER_STATE_DIR": str(Path(self.temp.name) / "user")
        }

    def choices(self) -> dict:
        return {
            "tracker_name": "linear",
            "tracker_values": {"team": "ENG"},
            "scm_name": "github",
            "scm_values": {"owner": "team", "repo": "project"},
            "artifacts_path": "docs/backlog",
            "base_branch": "main",
        }

    def test_fresh_repository_is_inspected_without_azure_default(self) -> None:
        with patch.dict(os.environ, self.preference_env):
            inspected = setup.inspect(self.repo).value
        self.assertEqual(inspected["status"], "missing")
        self.assertEqual(inspected["current_tracker"], {})
        self.assertIn("tracker.tracker", inspected["missing"])
        self.assertIn("linear", [item["name"] for item in inspected["trackers"]])
        command = subprocess.run(
            [sys.executable, str(CLI), "bootstrap", "--repo", str(self.repo)],
            capture_output=True,
            text=True,
            env={**os.environ, **self.preference_env},
        )
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout)["status"], "missing")
        self.assertFalse(settings.path(self.repo).exists())

    def test_proposal_applies_after_exact_review(self) -> None:
        with patch.dict(os.environ, self.preference_env):
            reviewed = setup.review(self.repo, **self.choices()).value
            self.assertEqual(reviewed["candidate"]["tracker"]["name"], "linear")
            applied = setup.apply(
                self.repo,
                reviewed["candidate"],
                reviewed["digest"],
                reviewed["source_digest"],
            )
            self.assertIsInstance(applied, Ok)
            self.assertEqual(settings.load(self.repo).value.tracker.name, "linear")
            self.assertIn(
                ".harness/state/", (self.repo / ".git/info/exclude").read_text()
            )

    def test_existing_custom_settings_survive_tracker_repair(self) -> None:
        target = settings.path(self.repo)
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "tracker": {
                        "name": "azure-devops",
                        "values": {
                            "organization": "your-organization",
                            "project": "your-project",
                        },
                    },
                    "scm": {
                        "name": "github",
                        "values": {"owner": "team", "repo": "project"},
                    },
                    "branch_template": "story/{key}-{slug}",
                    "artifacts_path": "Vault",
                    "git": {"base_branch": "develop"},
                    "checks": [{"name": "lint", "run": "make lint"}],
                }
            )
        )
        with patch.dict(os.environ, self.preference_env):
            reviewed = setup.review(
                self.repo, tracker_name="linear", tracker_values={"team": "ENG"}
            ).value
            self.assertEqual(
                reviewed["candidate"]["checks"], [{"name": "lint", "run": "make lint"}]
            )
            self.assertEqual(reviewed["candidate"]["artifacts_path"], "Vault")
            self.assertEqual(
                reviewed["candidate"]["branch_template"], "story/{key}-{slug}"
            )
            self.assertIsInstance(
                setup.apply(
                    self.repo,
                    reviewed["candidate"],
                    reviewed["digest"],
                    reviewed["source_digest"],
                ),
                Ok,
            )

    def test_changed_source_or_candidate_cannot_be_applied(self) -> None:
        reviewed = setup.review(self.repo, **self.choices()).value
        self.assertIsInstance(
            setup.apply(
                self.repo,
                {**reviewed["candidate"], "artifacts_path": "other"},
                reviewed["digest"],
                reviewed["source_digest"],
            ),
            Err,
        )
        settings.path(self.repo).parent.mkdir(parents=True)
        settings.path(self.repo).write_text("{}")
        self.assertIsInstance(
            setup.apply(
                self.repo,
                reviewed["candidate"],
                reviewed["digest"],
                reviewed["source_digest"],
            ),
            Err,
        )
        self.assertEqual(settings.path(self.repo).read_text(), "{}")

    def test_scm_is_inferred_from_git_remote(self) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "remote",
                "add",
                "origin",
                "git@github.com:team/project.git",
            ],
            check=True,
        )
        self.assertEqual(
            setup.inferred_scm(self.repo),
            {"name": "github", "values": {"owner": "team", "repo": "project"}},
        )


if __name__ == "__main__":
    unittest.main()
