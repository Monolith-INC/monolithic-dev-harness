"""Linear issue-kind labels are checked before the first publication write."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.result import Err, Ok
from integrations import readiness, registry

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


class ReadinessTests(unittest.TestCase):
    def active(self) -> registry.Active:
        manifest = registry.read_manifest(
            PLUGIN_ROOT / "trackers/linear", "shipped"
        ).value
        return registry.Active(manifest, {"team": "ENG"})

    def test_missing_story_and_task_labels_block_publication(self) -> None:
        seen = []

        def call(tool: str, arguments: dict):
            seen.append((tool, arguments))
            return Ok(
                {"labels": [{"name": "Epic"}, {"name": "Feature"}, {"name": "Bug"}]}
            )

        checked = readiness.check(self.active(), call).value
        self.assertFalse(checked.ready)
        self.assertEqual(checked.missing_labels, ("Story", "Task"))
        self.assertEqual(seen[0][0], "list_issue_labels")
        self.assertEqual(seen[0][1]["team"], "ENG")

    def test_all_labels_across_pages_are_accepted(self) -> None:
        def call(tool: str, arguments: dict):
            return (
                Ok(
                    {
                        "labels": [{"name": "Epic"}, {"name": "Feature"}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "next"},
                    }
                )
                if not arguments.get("cursor")
                else Ok(
                    {"labels": [{"name": "Story"}, {"name": "Task"}, {"name": "Bug"}]}
                )
            )

        self.assertTrue(readiness.check(self.active(), call).value.ready)

    def test_unreadable_reply_fails_closed(self) -> None:
        self.assertIsInstance(
            readiness.check(self.active(), lambda *_: Ok("error")), Err
        )


if __name__ == "__main__":
    unittest.main()
