"""The extracted integrations writer produces the Azure Boards + Azure Repos binding bootstrap relies on."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
for entry in (PLUGIN_ROOT, PLUGIN_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from harness.integrations_setup import configure_integrations  # noqa: E402


class TestConfigureIntegrations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(
            ["git", "init", "-q", "-b", "develop", str(self.repo)], check=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "remote",
                "add",
                "origin",
                "https://dev.azure.com/contoso/shop/_git/shop-monorepo",
            ],
            check=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def configure(self, **env: str) -> dict:
        with mock.patch.dict(os.environ, env, clear=False):
            if "AZURE_DEVOPS_ORG" not in env:
                os.environ.pop("AZURE_DEVOPS_ORG", None)
            path = configure_integrations(
                self.repo,
                tracker="azure_devops",
                scm="azure_repos",
                branch_template="{category}/{key}-{slug}",
                discover=False,
                runtime_dir=PLUGIN_ROOT,
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_binds_azure_boards_and_azure_repos(self) -> None:
        config = self.configure(AZURE_DEVOPS_ORG="contoso")
        self.assertEqual(config["schemaVersion"], 1)
        self.assertEqual(config["branchTemplate"], "{category}/{key}-{slug}")
        self.assertEqual(config["tracker"]["adapter"], "azure_devops")
        self.assertEqual(config["scm"]["adapter"], "azure_repos")
        self.assertIn("contoso", config["tracker"]["connection"]["args"])

    def test_org_falls_back_to_the_git_remote(self) -> None:
        config = self.configure()
        self.assertIn("contoso", config["scm"]["connection"]["args"])

    def test_branch_template_must_carry_the_work_item_key(self) -> None:
        with self.assertRaises(ValueError):
            configure_integrations(
                self.repo,
                tracker="azure_devops",
                scm="azure_repos",
                branch_template="{category}/{slug}",
                discover=False,
            )


if __name__ == "__main__":
    unittest.main()
