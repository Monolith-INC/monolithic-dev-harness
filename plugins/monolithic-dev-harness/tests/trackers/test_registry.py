from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness import state
from scripts.trackers.registry import (
    TrackerError,
    active,
    available,
    folder_digest,
    pin_approved_trackers,
)


def _manifest(name: str, *, status: str = "approved") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "name": name,
        "label": f"{name} tracker",
        "docs": "https://example.test/docs",
        "access": {"kind": "mcp", "server": "mcp.json", "auth": "oauth"},
        "settings": [],
        "artifacts": [
            {"name": "Feature", "children": ["Story"]},
            {"name": "Story", "children": ["Task"], "estimate": "points"},
            {"name": "Task", "children": []},
        ],
        "roles": {
            "containers": ["Feature"],
            "delivery_unit": "Story",
            "step": "Task",
        },
        "states": {
            "backlog": "New",
            "ready": "Ready",
            "in_progress": "Active",
            "done": "Done",
            "canceled": "Canceled",
        },
        "ids": {
            "pattern": "[A-Z]+-[0-9]+",
            "branch_key": "[0-9]+",
            "mention": ["#{id}"],
        },
        "attachments": {"spec": "comment", "report": "comment", "pull_request": "link"},
        "text_format": "markdown",
        "writes": ["tracker_write"],
        "sources": {"manifest": "https://example.test/docs"},
        "status": status,
    }


def _write_manifest(root: Path, name: str, *, status: str = "approved") -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "tracker.json").write_text(
        json.dumps(_manifest(name, status=status)), encoding="utf-8"
    )
    return folder


class RegistryTests(unittest.TestCase):
    def test_available_includes_shipped_and_only_pinned_onboarded_trackers(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shipped = _write_manifest(repo / "shipped", "azure-devops")
            onboarded = _write_manifest(repo / ".harness" / "trackers", "acme")

            self.assertEqual(
                [
                    tracker.name
                    for tracker in available(repo, shipped_root=shipped.parent)
                ],
                ["azure-devops"],
            )

            state.open_approval(repo, "HB-TRACKERS", 20)
            pin_approved_trackers(repo, "HB-TRACKERS", [onboarded])

            self.assertEqual(
                [
                    tracker.name
                    for tracker in available(repo, shipped_root=shipped.parent)
                ],
                ["acme", "azure-devops"],
            )

    def test_active_prefers_shipped_on_name_clash_without_explicit_onboarded_source(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shipped = _write_manifest(repo / "shipped", "acme")
            onboarded = _write_manifest(repo / ".harness" / "trackers", "acme")
            state.open_approval(repo, "HB-TRACKERS", 20)
            pin_approved_trackers(repo, "HB-TRACKERS", [onboarded])
            (repo / ".harness").mkdir(exist_ok=True)
            (repo / ".harness" / "integrations.json").write_text(
                json.dumps({"tracker": {"name": "acme"}}), encoding="utf-8"
            )

            self.assertEqual(active(repo, shipped_root=shipped.parent).root, shipped)

    def test_active_uses_pinned_onboarded_tracker_when_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shipped = _write_manifest(repo / "shipped", "acme")
            onboarded = _write_manifest(repo / ".harness" / "trackers", "acme")
            state.open_approval(repo, "HB-TRACKERS", 20)
            pin_approved_trackers(repo, "HB-TRACKERS", [onboarded])
            (repo / ".harness").mkdir(exist_ok=True)
            (repo / ".harness" / "integrations.json").write_text(
                json.dumps({"tracker": {"name": "acme", "source": "onboarded"}}),
                encoding="utf-8",
            )

            self.assertEqual(active(repo, shipped_root=shipped.parent).root, onboarded)

    def test_active_fails_closed_for_invalid_selected_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            folder = _write_manifest(repo / "shipped", "acme")
            (folder / "tracker.json").write_text("{}", encoding="utf-8")
            (repo / ".harness").mkdir(exist_ok=True)
            (repo / ".harness" / "integrations.json").write_text(
                json.dumps({"tracker": {"name": "acme"}}), encoding="utf-8"
            )

            with self.assertRaisesRegex(TrackerError, "schemaVersion"):
                active(repo, shipped_root=folder.parent)

    def test_shipped_manifests_are_discoverable(self):
        names = {tracker.name for tracker in available(Path.cwd())}
        self.assertTrue({"azure-devops", "linear", "local"} <= names)

    def test_digest_changes_when_an_onboarded_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = _write_manifest(Path(directory), "acme")
            before = folder_digest(folder)
            (folder / "instructions.md").write_text("first", encoding="utf-8")
            after = folder_digest(folder)

            self.assertNotEqual(before, after)
