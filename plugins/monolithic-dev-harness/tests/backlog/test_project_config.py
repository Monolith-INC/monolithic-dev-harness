import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator_core.project_config import (
    PLUGIN_DIRNAME,
    AzureConfig,
    ProjectConfig,
    config_path,
    load_project_config,
    org_from_mcp,
    plugin_dir,
    save_project_config,
    update_config,
)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ConfigTestCase(unittest.TestCase):
    """Base case with a clean environment, so host env vars cannot leak into assertions."""

    def setUp(self):
        self._env = patch.dict(os.environ, {}, clear=False)
        self._env.start()
        for key in list(os.environ):
            if key.startswith(("AGILE_WORKFLOW_", "AZURE_DEVOPS_", "ADO_", "CODEX_")):
                del os.environ[key]

    def tearDown(self):
        self._env.stop()


class TestNoAssumedArtifactsLocation(ConfigTestCase):
    """The core constraint: the plugin never invents a place to write."""

    def test_artifacts_path_has_no_default(self):
        """An unconfigured project has no artifacts location, and says so."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_project_config(Path(tmpdir))
            self.assertIsNone(config.artifacts_path)
            self.assertFalse(config.artifacts_ready)
            self.assertIsNone(config.resolve_artifacts_dir(Path(tmpdir)))

    def test_config_module_names_only_its_own_directory(self):
        """A regression guard: the plugin must name no storage location but its own.

        Naming a location for the user's work is how it once ended up creating a directory
        inside a client project that nobody asked for.
        """
        source = Path(__file__).resolve().parents[2] / (
            "runtime/orchestrator_core/project_config.py"
        )
        names = re.findall(
            r'^([A-Z_]+)\s*=\s*[("\']', source.read_text(encoding="utf-8"), re.M
        )
        self.assertIn("PLUGIN_DIRNAME", names)
        self.assertEqual(PLUGIN_DIRNAME, ".harness/backlog")
        # No constant may hold a candidate location for user artifacts.
        self.assertNotIn("DEFAULT_ARTIFACTS_PATH", names)

    def test_plugin_state_dir_is_not_the_artifacts_dir(self):
        """Plugin internals and user artifacts are separate places."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = ProjectConfig(artifacts_path="docs/backlog")
            self.assertEqual(plugin_dir(root), root / PLUGIN_DIRNAME)
            self.assertNotEqual(config.resolve_artifacts_dir(root), plugin_dir(root))

    def test_resolving_does_not_create_the_directory(self):
        """Resolving a path must not bring it into existence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            resolved = ProjectConfig(
                artifacts_path="nowhere/yet"
            ).resolve_artifacts_dir(root)
            self.assertEqual(resolved, root / "nowhere" / "yet")
            self.assertFalse(resolved.exists())


class TestArtifactsPathResolution(ConfigTestCase):
    """How a supplied path is interpreted."""

    def test_relative_path_is_taken_from_the_project_root(self):
        """A relative path belongs to the project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = ProjectConfig(artifacts_path="docs/tickets")
            self.assertEqual(
                config.resolve_artifacts_dir(root), root / "docs" / "tickets"
            )

    def test_absolute_path_is_used_as_given(self):
        """An absolute path may point anywhere the user likes, including outside the repo."""
        config = ProjectConfig(artifacts_path="/somewhere/else")
        self.assertEqual(
            config.resolve_artifacts_dir(Path("/project")), Path("/somewhere/else")
        )

    def test_user_home_is_expanded(self):
        """A ~ path resolves to the user's home."""
        resolved = ProjectConfig(artifacts_path="~/notes").resolve_artifacts_dir(
            Path("/project")
        )
        self.assertEqual(resolved, Path.home() / "notes")

    def test_the_plugin_does_not_care_what_is_at_the_path(self):
        """Any directory the user names is read the same way, whatever else lives there."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for candidate in ("anything", "docs", "../shared/backlog"):
                config = ProjectConfig(artifacts_path=candidate)
                self.assertIsNotNone(config.resolve_artifacts_dir(root))


class TestConfigFile(ConfigTestCase):
    """The canonical .agile-backlog-toolkit/config.json."""

    def test_reads_all_fields(self):
        """Every value round-trips out of the canonical file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                config_path(root),
                {
                    "artifacts_path": "docs/backlog",
                    "provider_mode": "both",
                    "azure": {
                        "org": "o",
                        "project": "p",
                        "team": "t",
                        "process": "scrum",
                    },
                    "linear": {"team": "linear-team"},
                },
            )
            config = load_project_config(root)
            self.assertEqual(config.artifacts_path, "docs/backlog")
            self.assertEqual(config.azure.org, "o")
            self.assertEqual(config.azure.process, "scrum")
            self.assertEqual(config.provider_mode, "both")
            self.assertEqual(config.linear.team, "linear-team")

    def test_malformed_file_degrades_without_inventing_a_path(self):
        """Broken JSON must neither crash nor conjure an artifacts location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = config_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("{not json", encoding="utf-8")
            config = load_project_config(root)
            self.assertIsNone(config.artifacts_path)

    def test_blank_values_are_treated_as_unset(self):
        """An empty string is not a configured value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(config_path(root), {"artifacts_path": "   ", "azure": {"org": ""}})
            config = load_project_config(root)
            self.assertIsNone(config.artifacts_path)
            self.assertEqual(config.missing(), ["org", "project"])


class TestFallbackSources(ConfigTestCase):
    """What older files can and cannot supply."""

    def test_unrecognised_keys_do_not_become_an_artifacts_path(self):
        """Only `artifacts_path` sets the artifacts path.

        A key this version does not recognise is not a user telling it where artifacts go,
        so the path stays unset -- which makes the caller ask, the correct outcome.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(config_path(root), {"storage": "SomeFolder", "output_dir": "Other"})
            _write(
                root / ".agile-backlog-toolkit.install.json", {"output_folder": "Third"}
            )
            self.assertIsNone(load_project_config(root).artifacts_path)

    def test_install_manifest_supplies_org(self):
        """A project installed by an older version still knows its organisation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                plugin_dir(root) / "install.json", {"azure_devops_org": "legacy-org"}
            )
            self.assertEqual(load_project_config(root).azure.org, "legacy-org")

    def test_an_unmigrated_project_is_still_read_from_its_old_folder(self):
        """Until bootstrap moves it, the pre-0.1.6 layout keeps working."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / ".agile-backlog-toolkit" / "config.json",
                {"azure": {"project": "p"}},
            )
            _write(
                root / ".agile-backlog-toolkit.install.json", {"azure_devops_org": "o"}
            )
            config = load_project_config(root)
            self.assertEqual((config.azure.org, config.azure.project), ("o", "p"))
            self.assertEqual(plugin_dir(root), root / ".agile-backlog-toolkit")

    def test_canonical_file_wins_over_fallbacks(self):
        """A current value is not overridden by an older source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(config_path(root), {"azure": {"org": "current"}})
            _write(plugin_dir(root) / "install.json", {"azure_devops_org": "stale"})
            self.assertEqual(load_project_config(root).azure.org, "current")

    def test_sources_compose_across_files(self):
        """Each source fills only what earlier ones left unset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(config_path(root), {"azure": {"project": "p"}})
            _write(plugin_dir(root) / "install.json", {"azure_devops_org": "o"})
            config = load_project_config(root)
            self.assertEqual((config.azure.org, config.azure.project), ("o", "p"))


class TestOrgFromMcp(ConfigTestCase):
    """Extracting the organisation from an MCP server definition."""

    def test_npx_and_pinned_node_invocations(self):
        """The org is the trailing argument in both launch forms."""
        npx = {
            "mcpServers": {
                "azure-devops": {"args": ["-y", "@azure-devops/mcp@2.7.0", "my-org"]}
            }
        }
        node = {
            "mcpServers": {"azure-devops": {"args": ["/x/dist/index.js", "my-org"]}}
        }
        self.assertEqual(org_from_mcp(npx), "my-org")
        self.assertEqual(org_from_mcp(node), "my-org")

    def test_alternate_server_key(self):
        """Some setups name the server 'Azure DevOps'."""
        self.assertEqual(
            org_from_mcp(
                {"mcpServers": {"Azure DevOps": {"args": ["/x/dist/index.js", "org"]}}}
            ),
            "org",
        )

    def test_hostile_inputs(self):
        """Malformed MCP files yield nothing rather than raising."""
        for payload in (
            None,
            {},
            {"mcpServers": None},
            {"mcpServers": {"azure-devops": "text"}},
        ):
            self.assertIsNone(org_from_mcp(payload))

    def test_org_recovered_from_mcp_wiring(self):
        """A project with only MCP wired still knows its organisation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / ".mcp.json",
                {"mcpServers": {"azure-devops": {"args": ["/x.js", "my-org"]}}},
            )
            config = load_project_config(root)
            self.assertEqual(config.azure.org, "my-org")
            self.assertIn(".mcp.json", config.sources)


class TestEnvironmentOverrides(ConfigTestCase):
    """Environment wins, so CI can override a committed file."""

    def test_env_beats_config_file(self):
        """An env var overrides the stored value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(config_path(root), {"azure": {"org": "from-file"}})
            with patch.dict(os.environ, {"AGILE_WORKFLOW_AZURE_ORG": "from-env"}):
                config = load_project_config(root)
                self.assertEqual(config.azure.org, "from-env")
                self.assertEqual(config.sources[0], "environment")

    def test_artifacts_path_can_be_overridden(self):
        """A one-off run can redirect output without editing anything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                os.environ, {"AGILE_WORKFLOW_ARTIFACTS_PATH": "/tmp/elsewhere"}
            ):
                self.assertEqual(
                    load_project_config(Path(tmpdir)).artifacts_path, "/tmp/elsewhere"
                )

    def test_ado_prefixed_vars_recognised(self):
        """The ADO_* names used by the live smoke test also work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"ADO_PROJECT": "p", "ADO_TEAM": "t"}):
                config = load_project_config(Path(tmpdir))
                self.assertEqual((config.azure.project, config.azure.team), ("p", "t"))


class TestMissingValues(ConfigTestCase):
    """What has to be asked for."""

    def test_org_and_project_are_required(self):
        """Both are needed before any Azure call can be made."""
        self.assertEqual(ProjectConfig().missing(), ["org", "project"])

    def test_team_is_optional_unless_asked_for(self):
        """Team only counts as missing when the caller says it is required."""
        config = ProjectConfig(azure=AzureConfig(org="o", project="p"))
        self.assertEqual(config.missing(), [])
        self.assertTrue(config.azure_ready)
        self.assertEqual(config.missing(require_team=True), ["team"])


class TestPersistence(ConfigTestCase):
    """Saving, which is what lazy fill relies on."""

    def test_save_and_reload_round_trips(self):
        """What is written is what comes back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            save_project_config(
                root,
                ProjectConfig(
                    artifacts_path="docs", azure=AzureConfig(org="o", project="p")
                ),
            )
            config = load_project_config(root)
            self.assertEqual(config.artifacts_path, "docs")
            self.assertEqual(config.azure.project, "p")

    def test_update_merges_without_clobbering(self):
        """Filling in the team must not erase the org or the path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            update_config(root, artifacts_path="docs", org="o", project="p")
            update_config(root, team="t")
            config = load_project_config(root)
            self.assertEqual(config.artifacts_path, "docs")
            self.assertEqual((config.azure.org, config.azure.team), ("o", "t"))

    def test_unknown_keys_survive_a_write(self):
        """A hand-added key must not be destroyed by a lazy-fill save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(config_path(root), {"customTeamSetting": 42})
            update_config(root, org="o")
            reloaded = json.loads(config_path(root).read_text(encoding="utf-8"))
            self.assertEqual(reloaded["customTeamSetting"], 42)
            self.assertEqual(reloaded["azure"]["org"], "o")

    def test_empty_values_do_not_blank_existing_ones(self):
        """Passing None must not erase what is already set."""
        config = ProjectConfig(artifacts_path="docs", azure=AzureConfig(org="o"))
        updated = config.with_azure(org=None).with_artifacts_path("")
        self.assertEqual(updated.azure.org, "o")
        self.assertEqual(updated.artifacts_path, "docs")

    def test_unset_artifacts_path_is_not_written(self):
        """A config with no path must not persist a placeholder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            save_project_config(root, ProjectConfig(azure=AzureConfig(org="o")))
            data = json.loads(config_path(root).read_text(encoding="utf-8"))
            self.assertNotIn("artifacts_path", data)

    def test_save_failure_returns_none_rather_than_raising(self):
        """An unwritable location degrades, following the never-raise idiom."""
        with tempfile.TemporaryDirectory() as tmpdir:
            blocker = Path(tmpdir) / PLUGIN_DIRNAME
            blocker.parent.mkdir(parents=True)
            blocker.write_text("not a directory", encoding="utf-8")
            self.assertIsNone(save_project_config(Path(tmpdir), ProjectConfig()))


if __name__ == "__main__":
    unittest.main()
