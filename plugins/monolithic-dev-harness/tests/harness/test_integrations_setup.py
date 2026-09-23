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

from harness.integrations_setup import (  # noqa: E402
    _azure_remote,
    configure_integrations,
    repair_integrations,
)


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


def _repo_with_remote(root: Path, url: str) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", url], check=True)
    return root


class TestAzureRemote(unittest.TestCase):
    def test_ssh_and_https_remotes_give_org_project_repo(self) -> None:
        for url in (
            "git@ssh.dev.azure.com:v3/contoso/fabrikam/web-app",
            "https://contoso@dev.azure.com/contoso/fabrikam/_git/web-app",
        ):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmp:
                repo = _repo_with_remote(Path(tmp), url)
                self.assertEqual(
                    _azure_remote(repo), ("contoso", "fabrikam", "web-app")
                )


class TestBootstrapProject(unittest.TestCase):
    def test_bootstrap_writes_the_project_the_policy_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _repo_with_remote(
                Path(tmp), "git@ssh.dev.azure.com:v3/contoso/from-remote/web-app"
            )
            path = configure_integrations(
                repo,
                tracker="azure_devops",
                scm="azure_repos",
                branch_template="{category}/{key}-{slug}",
                discover=False,
                runtime_dir=PLUGIN_ROOT,
                project="fabrikam",
                repository="monorepo",
            )
            config = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(config["tracker"]["project"], "fabrikam")
        self.assertEqual(
            (config["scm"]["project"], config["scm"]["repository"]),
            ("fabrikam", "monorepo"),
        )
        # The Azure adapters call their tools by name, so nothing is bound.
        self.assertNotIn("bindings", config["tracker"])
        self.assertNotIn("bindings", config["scm"])


class TestRepairIntegrations(unittest.TestCase):
    """A config written by 0.1.1 is brought up to date in place."""

    AZURE = {
        "organization": "contoso",
        "project": "fabrikam",
        "repository": "monorepo",
    }

    def _write(self, directory: str, config: dict) -> Path:
        path = Path(directory) / "integrations.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_fills_the_project_and_fixes_a_misread_ssh_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                {
                    "schemaVersion": 1,
                    "branchTemplate": "{category}/{key}-{slug}",
                    "tracker": {
                        "adapter": "azure_devops",
                        "bindings": {"get_work_item": "wit_get_work_item"},
                        "mappings": {"kinds": {"epic": "Epic"}},
                    },
                    "scm": {
                        "adapter": "azure_repos",
                        "organization": "v3",
                        "project": "contoso",
                        "repository": "fabrikam",
                    },
                },
            )
            repairs = repair_integrations(path, self.AZURE)
            config = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(config["tracker"]["project"], "fabrikam")
        self.assertEqual(
            [config["scm"][k] for k in ("organization", "project", "repository")],
            ["contoso", "fabrikam", "monorepo"],
        )
        self.assertNotIn("bindings", config["tracker"])
        # Everything else is left as it was.
        self.assertEqual(config["tracker"]["mappings"], {"kinds": {"epic": "Epic"}})
        self.assertEqual(len(repairs), 5)

    def test_a_current_config_is_left_alone(self) -> None:
        current = {
            "tracker": {"adapter": "azure_devops", "project": "fabrikam"},
            "scm": {"adapter": "azure_repos", **self.AZURE},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, current)
            before = path.read_text(encoding="utf-8")
            self.assertEqual(repair_integrations(path, self.AZURE), [])
            self.assertEqual(path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
