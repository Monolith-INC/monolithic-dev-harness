from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.result import Err, Ok, err
from harness.settings import parse
from integrations import registry, trust
from integrations.contracts import TrackerOps
from tests.settings_fixture import MINIMAL

from .fakes import FakeTransport, copy_tracker

SETTINGS = {
    "schemaVersion": 1,
    "scm": {"name": "github", "values": {"owner": "o", "repo": "r"}},
    "branch_template": "feature/{key}-{slug}",
}


def settings(tracker: dict):
    return parse({**MINIMAL, "tracker": tracker})


class RegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.onboarded = self.repo / ".harness" / "trackers"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_every_shipped_tracker_meets_the_contract(self) -> None:
        results = registry.shipped()
        self.assertEqual([type(result) for result in results], [Ok, Ok, Ok])
        self.assertEqual(
            [result.value.name for result in results],
            ["azure-devops", "linear", "local"],
        )

    def test_every_shipped_adapter_builds_its_operations(self) -> None:
        values = {
            "azure-devops": {"organization": "o", "project": "p"},
            "linear": {"team": "ENG"},
            "local": {},
        }
        for manifest in registry.usable(self.repo):
            built = registry.build(
                registry.Active(manifest, values[manifest.name]),
                self.repo,
                FakeTransport({}),
            )
            self.assertIsInstance(built.value, TrackerOps, manifest.name)

    def test_a_broken_folder_is_reported_alone(self) -> None:
        copy_tracker("local", self.onboarded / "broken", kinds={"epic": "nope"})
        copy_tracker("local", self.onboarded / "fine", name="fine")
        trust.trust(
            self.repo,
            "fine",
            self.onboarded / "fine",
            trust.digest(self.onboarded / "fine"),
        )
        names = [manifest.name for manifest in registry.usable(self.repo)]
        self.assertIn("fine", names)
        self.assertIn("azure-devops", names)
        [problem] = registry.problems(self.repo)
        self.assertIn("'broken'", problem.message)

    def test_the_manifest_rules_beyond_the_schema(self) -> None:
        cases = {
            "cycle": {
                "artifacts": [
                    {"name": "a", "children": ["b"]},
                    {"name": "b", "children": ["a"]},
                ]
            },
            "hierarchy": {
                "artifacts": [
                    {"name": n, "children": []}
                    for n in ("epic", "feature", "user_story", "task", "bug")
                ]
            },
            "branch key": {
                "ids": {
                    "pattern": "[0-9]+",
                    "branch_key": "[0-9]+",
                    "mention": [],
                    "mentions_link": False,
                }
            },
            "mention": {
                "ids": {
                    "pattern": "[0-9]+",
                    "branch_key": "(?P<id>[0-9]+)",
                    "mention": ["#x"],
                    "mentions_link": True,
                }
            },
            "regex": {
                "ids": {
                    "pattern": "[0-9",
                    "branch_key": "(?P<id>[0-9]+)",
                    "mention": [],
                    "mentions_link": False,
                }
            },
            "placeholder": {
                "connection": {"kind": "mcp", "command": "x", "args": ["{token}"]}
            },
            "reply keys": {
                "planning": {
                    "replies": [
                        {"key": "cycle", "description": "one"},
                        {"key": "cycle", "description": "two"},
                    ]
                }
            },
            "no planning": {"planning": None},
        }
        for label, change in cases.items():
            folder = copy_tracker(
                "local", self.repo / label.replace(" ", "-"), **change
            )
            self.assertIsInstance(
                registry.read_manifest(folder, "onboarded"), Err, label
            )

    def test_the_manifest_declares_the_replies_planning_reads(self) -> None:
        manifest = registry.read_manifest(
            registry.SHIPPED_ROOT / "azure-devops", "shipped"
        ).value
        self.assertEqual(
            tuple(reply.key for reply in manifest.planning),
            ("iteration", "capacities", "team_settings", "work_items"),
        )

    def test_a_wide_diamond_hierarchy_is_checked_quickly(self) -> None:
        import time

        layers = [[f"l{depth}n{i}" for i in range(12)] for depth in range(12)]
        extra = [
            {
                "name": name,
                "children": layers[depth + 1] if depth + 1 < len(layers) else [],
            }
            for depth, layer in enumerate(layers)
            for name in layer
        ]
        local = json.loads(
            (registry.SHIPPED_ROOT / "local" / "tracker.json").read_text()
        )
        folder = copy_tracker(
            "local", self.repo / "wide", artifacts=local["artifacts"] + extra
        )
        started = time.monotonic()
        self.assertIsInstance(registry.read_manifest(folder, "onboarded"), Ok)
        self.assertLess(time.monotonic() - started, 1)

    def test_a_folder_without_an_adapter_is_rejected(self) -> None:
        folder = copy_tracker("local", self.repo / "noadapter")
        (folder / "adapter.py").unlink()
        self.assertIn(
            "adapter.py", registry.read_manifest(folder, "onboarded").failure.message
        )

    def test_onboarded_trackers_count_only_while_trusted_as_they_read(self) -> None:
        folder = copy_tracker("local", self.onboarded / "custom", name="custom")
        chosen = settings({"name": "custom", "source": "onboarded"})
        self.assertIsInstance(registry.resolve(self.repo, chosen), registry.Invalid)
        self.assertIsInstance(trust.trust(self.repo, "custom", folder, "0" * 12), Err)
        self.assertIsInstance(
            trust.trust(self.repo, "custom", folder, trust.digest(folder)[:12]), Ok
        )
        self.assertIsInstance(registry.resolve(self.repo, chosen), registry.Active)
        (folder / "adapter.py").write_text(
            (folder / "adapter.py").read_text() + "\n# changed\n"
        )
        resolution = registry.resolve(self.repo, chosen)
        self.assertIsInstance(resolution, registry.Invalid)
        self.assertEqual(resolution.failure.code, "untrusted_tracker")

    def test_resolution_is_invalid_for_bad_settings_or_values(self) -> None:
        self.assertIsInstance(
            registry.resolve(self.repo, err("invalid_settings", "x")), registry.Invalid
        )
        missing = registry.resolve(
            self.repo,
            settings({"name": "azure-devops", "values": {"organization": "o"}}),
        )
        self.assertIn("project", missing.failure.message)
        unknown = registry.resolve(
            self.repo, settings({"name": "local", "values": {"token": "x"}})
        )
        self.assertIn("token", unknown.failure.message)
        self.assertIsInstance(
            registry.resolve(self.repo, settings({"name": "nothing"})), registry.Invalid
        )
        active = registry.resolve(
            self.repo,
            settings(
                {
                    "name": "azure-devops",
                    "values": {"organization": "o", "project": "p"},
                }
            ),
        )
        self.assertEqual(active.manifest.name, "azure-devops")

    def test_connection_values_fill_the_command(self) -> None:
        active = registry.resolve(
            self.repo,
            settings(
                {
                    "name": "azure-devops",
                    "values": {"organization": "contoso", "project": "p"},
                }
            ),
        )
        command, args = registry.connection_command(
            active.manifest, active.values, self.repo
        )
        self.assertEqual((command, args[2]), ("npx", "contoso"))

    def test_loading_an_adapter_leaves_its_folder_and_trust_unchanged(self) -> None:
        folder = copy_tracker("local", self.onboarded / "custom", name="custom")
        trust.trust(self.repo, "custom", folder, trust.digest(folder))
        chosen = settings({"name": "custom", "source": "onboarded"})
        for _ in range(2):
            active = registry.resolve(self.repo, chosen)
            self.assertIsInstance(active, registry.Active)
            self.assertIsInstance(
                registry.build(active, self.repo, FakeTransport({})), Ok
            )
        self.assertFalse((folder / "__pycache__").exists())

    def test_an_adapter_that_raises_while_building_is_reported(self) -> None:
        folder = copy_tracker("local", self.onboarded / "boom", name="boom")
        (folder / "adapter.py").write_text(
            "def adapter(context):\n    raise KeyError('x')\n"
        )
        trust.trust(self.repo, "boom", folder, trust.digest(folder))
        active = registry.resolve(
            self.repo, settings({"name": "boom", "source": "onboarded"})
        )
        self.assertIn(
            "adapter(context) failed",
            registry.build(active, self.repo, FakeTransport({})).failure.message,
        )

    def test_an_adapter_that_breaks_the_contract_is_rejected(self) -> None:
        folder = copy_tracker("local", self.onboarded / "bad", name="bad")
        (folder / "adapter.py").write_text("def adapter(context):\n    return {}\n")
        trust.trust(self.repo, "bad", folder, trust.digest(folder))
        active = registry.resolve(
            self.repo, settings({"name": "bad", "source": "onboarded"})
        )
        self.assertIn(
            "did not return TrackerOps",
            registry.build(active, self.repo, FakeTransport({})).failure.message,
        )


class ManifestFileTest(unittest.TestCase):
    def test_shipped_manifests_are_json_objects_with_schema_version_1(self) -> None:
        for folder in sorted(registry.SHIPPED_ROOT.iterdir()):
            self.assertEqual(
                json.loads((folder / "tracker.json").read_text())["schemaVersion"], 1
            )
