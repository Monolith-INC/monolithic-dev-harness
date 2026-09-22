import tempfile
import unittest
from pathlib import Path

from scripts.policy.git_stack_merge_guard import (
    STAGE_NAME,
    evaluate_git_stack_merge_guard,
)


class GitStackMergeGuardTests(unittest.TestCase):
    def test_allows_when_stage_inactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            decision = evaluate_git_stack_merge_guard(
                "git rebase origin/feature/x", tmp
            )
            self.assertFalse(decision.is_denied())

    def test_denies_rebase_when_stage_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / ".codex-workflows" / "active-stage"
            stage.parent.mkdir(parents=True)
            stage.write_text(STAGE_NAME, encoding="utf-8")
            decision = evaluate_git_stack_merge_guard(
                "git rebase origin/feature/x", tmp
            )
            self.assertTrue(decision.is_denied())
            self.assertIn("rebase", decision.reason)

    def test_denies_force_push_when_stage_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / ".codex-workflows" / "active-stage"
            stage.parent.mkdir(parents=True)
            stage.write_text(STAGE_NAME, encoding="utf-8")
            decision = evaluate_git_stack_merge_guard(
                "git push --force-with-lease origin HEAD", tmp
            )
            self.assertTrue(decision.is_denied())

    def test_allows_merge_no_ff_when_stage_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / ".codex-workflows" / "active-stage"
            stage.parent.mkdir(parents=True)
            stage.write_text(STAGE_NAME, encoding="utf-8")
            decision = evaluate_git_stack_merge_guard(
                "git merge --no-ff feature/7313-x", tmp
            )
            self.assertFalse(decision.is_denied())


if __name__ == "__main__":
    unittest.main()
