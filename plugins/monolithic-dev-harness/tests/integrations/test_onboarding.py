from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

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
        self.assertIn(f"harness trust-tracker custom {digest[:12]}", summary)
        self.assertIn("trusted as it reads now: no", summary)
        self.assertIn("Read adapter.py in full", summary)
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
