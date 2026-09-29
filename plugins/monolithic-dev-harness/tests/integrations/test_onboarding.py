from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from core.result import Ok
from integrations import onboarding, registry, trust

from .fakes import copy_tracker


class OnboardingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.source = copy_tracker(
            "local", Path(self._tmp.name) / "source", name="custom"
        )

    def test_stage_then_show_then_trust(self) -> None:
        staged = onboarding.stage(self.repo, self.source).value
        self.assertEqual(staged, self.repo / ".harness" / "trackers" / "custom")
        summary = onboarding.show(self.repo, "custom").value
        digest = trust.digest(staged)
        self.assertNotIn("harness trust-tracker", summary)
        self.assertIn(trust.short_id("custom", digest), summary)
        self.assertIn("trusted as it reads now: no", summary)
        self.assertIn("adapter.py in full", summary)
        trust.trust(self.repo, "custom", staged, digest[:12])
        self.assertIn(
            "trusted as it reads now: yes", onboarding.show(self.repo, "custom").value
        )
        self.assertIn(
            "custom", [manifest.name for manifest in registry.usable(self.repo)]
        )

    def test_stage_refuses_invalid_links_shipped_names_and_repeats(self) -> None:
        broken = copy_tracker(
            "local", Path(self._tmp.name) / "broken", name="broken", kinds={"epic": "x"}
        )
        self.assertEqual(
            onboarding.stage(self.repo, broken).failure.code, "invalid_tracker"
        )
        linked = copy_tracker("local", Path(self._tmp.name) / "linked", name="linked")
        os.symlink("/etc/hostname", linked / "notes.md")
        self.assertIn("links", onboarding.stage(self.repo, linked).failure.message)
        shipped = copy_tracker("local", Path(self._tmp.name) / "shadow")
        self.assertEqual(
            onboarding.stage(self.repo, shipped).failure.code, "tracker_exists"
        )
        onboarding.stage(self.repo, self.source)
        self.assertEqual(
            onboarding.stage(self.repo, self.source).failure.code, "tracker_exists"
        )

    def test_show_needs_a_staged_folder(self) -> None:
        self.assertEqual(
            onboarding.show(self.repo, "nothing").failure.code, "unknown_tracker"
        )


class ClickOnboardingTest(unittest.TestCase):
    """Staging keeps the tracker's settings with it; selecting needs trust and every required value."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / ".harness" / "settings.json").write_text(
            '{\n  "schemaVersion": 1,\n  "tracker": {"name": "local"},\n'
            '  "scm": {"name": "github"},\n  "branch_template": "{key}"\n}\n'
        )
        settings = [{"key": "org", "required": True, "description": "Organization."}]
        self.source = copy_tracker(
            "local", Path(self._tmp.name) / "source", name="acme", settings=settings
        )

    def test_stage_keeps_the_values_and_the_summary_asks_by_question(self) -> None:
        staged = onboarding.stage(self.repo, self.source, {"org": "monolith"}).value
        self.assertEqual(
            json.loads((staged / "values.json").read_text()), {"org": "monolith"}
        )
        summary = onboarding.show(self.repo, "acme").value
        self.assertNotIn("harness trust-tracker", summary)
        self.assertIn("org = monolith", summary)
        self.assertIn(trust.short_id("acme", trust.digest(staged)), summary)
        self.assertIn('"Trust"', summary)

    def test_stage_refuses_values_the_tracker_does_not_take(self) -> None:
        self.assertEqual(
            onboarding.stage(self.repo, self.source, {"nope": "x"}).failure.code,
            "invalid_settings",
        )

    def test_select_needs_trust(self) -> None:
        onboarding.stage(self.repo, self.source, {"org": "monolith"})
        self.assertEqual(
            onboarding.select(self.repo, "acme").failure.code, "untrusted_tracker"
        )

    def test_stage_refuses_missing_or_empty_required_values(self) -> None:
        for values in ({}, {"org": ""}, {"org": "  "}):
            with self.subTest(values=values):
                failure = onboarding.stage(self.repo, self.source, values).failure
                self.assertEqual(failure.code, "invalid_settings")
                self.assertIn("--value org=", failure.message)
        self.assertFalse((self.repo / ".harness" / "trackers" / "acme").exists())

    def test_write_tracker_refuses_a_settings_file_that_is_not_an_object(self) -> None:
        from core.result import Err
        from harness import settings

        (self.repo / ".harness" / "settings.json").write_text("[]")
        self.assertIsInstance(settings.write_tracker(self.repo, {"name": "x"}), Err)
        self.assertEqual((self.repo / ".harness" / "settings.json").read_text(), "[]")

    def test_select_writes_only_the_tracker_selection(self) -> None:
        staged = onboarding.stage(self.repo, self.source, {"org": "monolith"}).value
        trust.trust(self.repo, "acme", staged, trust.digest(staged))
        before = json.loads((self.repo / ".harness" / "settings.json").read_text())
        self.assertIsInstance(onboarding.select(self.repo, "acme"), Ok)
        after = json.loads((self.repo / ".harness" / "settings.json").read_text())
        self.assertEqual(
            after["tracker"],
            {"name": "acme", "source": "onboarded", "values": {"org": "monolith"}},
        )
        self.assertEqual(
            {k: v for k, v in after.items() if k != "tracker"},
            {k: v for k, v in before.items() if k != "tracker"},
        )

    def test_the_stage_command_takes_values(self) -> None:
        import subprocess
        import sys

        cli = Path(__file__).resolve().parents[2] / "scripts" / "harness" / "cli.py"
        result = subprocess.run(
            [
                sys.executable,
                str(cli),
                "tracker",
                "stage",
                str(self.source),
                "--repo",
                str(self.repo),
                "--value",
                "org=monolith",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("org = monolith", result.stdout)
        values = self.repo / ".harness" / "trackers" / "acme" / "values.json"
        self.assertEqual(json.loads(values.read_text()), {"org": "monolith"})

    def test_short_id_follows_the_folder_version(self) -> None:
        self.assertEqual(
            trust.short_id("acme", "a" * 64), trust.short_id("acme", "a" * 64)
        )
        self.assertNotEqual(
            trust.short_id("acme", "a" * 64), trust.short_id("acme", "b" * 64)
        )
        self.assertRegex(trust.short_id("acme", "a" * 64), r"^HT-[A-Z0-9]{6}$")
