import re
import tempfile
import unittest
from pathlib import Path

from orchestrator_core.project_config import (
    PLUGIN_DIRNAME,
    ProjectConfig,
    load_project_config,
    plugin_dir,
)
from tests.settings_fixture import write_settings


class ConfigTestCase(unittest.TestCase):
    """Base case: environment variables never feed the configuration, so none are cleared."""


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


class TestReadFromSettings(ConfigTestCase):
    """The backlog view of `.harness/settings.json`, the only source."""

    def test_reads_the_artifacts_path_and_nothing_about_the_tracker(self):
        """The tracker and its values are the registry's to read, not this view's."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_settings(
                root,
                tracker={"name": "linear", "values": {"team": "ENG"}},
                artifacts_path="docs/backlog",
            )
            self.assertEqual(
                load_project_config(root),
                ProjectConfig("docs/backlog", (".harness/settings.json",)),
            )

    def test_broken_or_missing_settings_give_an_empty_configuration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertEqual(load_project_config(root), ProjectConfig())
            (root / ".harness").mkdir()
            (root / ".harness" / "settings.json").write_text("{")
            self.assertEqual(load_project_config(root), ProjectConfig())
