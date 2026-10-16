"""Reading plan and spec notes from the artifacts path, and which of them the user approved."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.harness import local_artifacts, state
from tests.settings_fixture import write_settings


class LocalArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.vault = self.repo / "Vault"
        write_settings(self.repo, artifacts_path="Vault")

    def note(self, name: str, frontmatter: str, prefix: str = "") -> Path:
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"{prefix}---\n{frontmatter}\n---\n\n# Note\n", encoding="utf-8"
        )
        return path

    def approve(self, approval_id: str = "HB-Q0001") -> None:
        state.open_approval(self.repo, approval_id, 20)
        state.pin_notes(
            self.repo,
            approval_id,
            local_artifacts.reviewed_notes(
                self.repo, map(str, self.repo.rglob("*.md"))
            ),
        )

    def kinds(self, key: str = "7824") -> set[str]:
        return local_artifacts.approved_kinds_for(self.repo, key)

    # --- what an approval pins -----------------------------------------------------------

    def test_only_reviewed_notes_in_the_artifacts_path_are_pinned(self) -> None:
        reviewed = self.note("plan.md", "type: implementation-plan\nstatus: draft")
        self.note("other.md", "type: implementation-plan\nstatus: draft")
        untyped = self.note("none.md", "story: 7824")
        outside = self.repo / "elsewhere.md"
        outside.write_text("---\ntype: spec\n---\n", encoding="utf-8")
        self.assertEqual(
            set(
                local_artifacts.reviewed_notes(
                    self.repo, [str(reviewed), str(untyped), str(outside)]
                )
            ),
            {str(reviewed.resolve())},
        )

    def test_no_artifacts_path_pins_nothing(self) -> None:
        write_settings(self.repo)
        path = self.note("plan.md", "type: spec")
        self.assertIsNone(local_artifacts.artifacts_dir(self.repo))
        self.assertEqual(local_artifacts.reviewed_notes(self.repo, [str(path)]), {})

    def test_marking_a_pinned_note_active_keeps_the_pin(self) -> None:
        path = self.note("s.md", "type: spec\nstory: 7824\nstatus: draft")
        self.approve()
        path.write_text(
            path.read_text(encoding="utf-8").replace("status: draft", "status: active"),
            encoding="utf-8",
        )
        self.assertEqual(self.kinds(), {"spec"})

    # --- what counts as approved now -----------------------------------------------------

    def test_a_pinned_note_naming_the_key_reports_its_raw_type(self) -> None:
        self.note("plan.md", 'type: Implementation-Plan\nstory: "7824"')
        self.approve()
        self.assertEqual(self.kinds(), {"Implementation-Plan"})

    def test_the_reader_does_not_decide_what_a_spec_is(self) -> None:
        self.note("s.md", "type: session\nstory: 7824")
        self.approve()
        self.assertEqual(self.kinds(), {"session"})

    def test_list_and_numeric_keys_match(self) -> None:
        self.note("a.md", 'type: spec\nstory: ["7823", "7824"]')
        self.note("b.md", "type: adr\nwork_item: 7824")
        self.approve()
        self.assertEqual(self.kinds(), {"spec", "adr"})

    def test_ticket_names_the_parent_and_is_ignored(self) -> None:
        self.note("s.md", "type: spec\nticket: 7824")
        self.approve()
        self.assertEqual(self.kinds(), set())

    def test_nothing_counts_before_an_approval(self) -> None:
        self.note("s.md", "type: spec\nstory: 7824")
        self.assertEqual(self.kinds(), set())

    def test_an_edit_after_the_approval_unpins(self) -> None:
        path = self.note("s.md", "type: spec\nstory: 7824")
        self.approve()
        path.write_text(path.read_text(encoding="utf-8") + "more\n", encoding="utf-8")
        self.assertEqual(self.kinds(), set())

    def test_a_later_approval_pins_the_new_content(self) -> None:
        path = self.note("s.md", "type: spec\nstory: 7824")
        self.approve("HB-Q0001")
        path.write_text(path.read_text(encoding="utf-8") + "more\n", encoding="utf-8")
        self.approve("HB-Q0002")
        self.assertEqual(self.kinds(), {"spec"})

    def test_a_revoked_approval_unpins(self) -> None:
        self.note("s.md", "type: spec\nstory: 7824")
        self.approve()
        state.revoke_approvals(self.repo)
        self.assertEqual(self.kinds(), set())

    def test_a_deleted_note_is_skipped(self) -> None:
        path = self.note("s.md", "type: spec\nstory: 7824")
        self.approve()
        path.unlink()
        self.assertEqual(self.kinds(), set())

    def test_frontmatter_after_a_byte_order_mark_is_read(self) -> None:
        self.note("s.md", "type: spec\nstory: 7824", prefix="﻿")
        self.approve()
        self.assertEqual(self.kinds(), {"spec"})

    # --- where the artifacts path comes from ---------------------------------------------

    def test_the_settings_file_is_the_only_source(self) -> None:
        with tempfile.TemporaryDirectory() as elsewhere:
            with mock.patch.dict(
                os.environ, {"AGILE_WORKFLOW_ARTIFACTS_PATH": elsewhere}
            ):
                self.assertEqual(
                    local_artifacts.artifacts_dir(self.repo), self.repo / "Vault"
                )

    def test_home_is_expanded(self) -> None:
        write_settings(self.repo, artifacts_path="~/vault")
        with mock.patch.dict(os.environ, {"HOME": "/home/someone"}):
            self.assertEqual(
                local_artifacts.artifacts_dir(self.repo), Path("/home/someone/vault")
            )


if __name__ == "__main__":
    unittest.main()
