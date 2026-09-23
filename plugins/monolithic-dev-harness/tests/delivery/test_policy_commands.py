"""The workflow policy reads commands through the shared reader, like the harness rules."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.hook_runtime import _is_mutating_git
from scripts.policy.commands import writes_inside
from scripts.policy.git_branch_guard import evaluate_git_branch_guard


class WritesInsideTests(unittest.TestCase):
    def test_redirecting_output_is_not_a_file_write(self) -> None:
        # Reported from a real session: these were blocked because they contain `>`.
        with tempfile.TemporaryDirectory() as tmp:
            for command in (
                "ls -la 2>&1",
                "harness doctor 2>/dev/null",
                "git status 2>&1 | head",
                "cat README.md > /tmp/copy.md",
                # Tools it doesn't know are not assumed to write: that is for the protection rules.
                "flutter test test/widget_test.dart",
                "npm run lint",
            ):
                with self.subTest(command=command):
                    self.assertFalse(writes_inside(command, tmp))

    def test_writing_into_the_repository_is(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for command in (
                "echo x > notes.md",
                "cp /tmp/a lib/a.dart",
                "sed -i s/a/b/ lib/a.dart",
                f"echo x > {tmp}/notes.md",
            ):
                with self.subTest(command=command):
                    self.assertTrue(writes_inside(command, tmp))


class MutatingGitTests(unittest.TestCase):
    def test_every_git_on_the_line_counts(self) -> None:
        for command in (
            "git status && git commit -m x",
            "sudo git push",
            "(git merge develop)",
        ):
            with self.subTest(command=command):
                self.assertTrue(_is_mutating_git(command))
        self.assertFalse(_is_mutating_git("git status && git log"))


class ProtectedBranchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        subprocess.run(["git", "init", "-q", "-b", "develop", self.repo], check=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_commit_after_a_read_is_still_blocked_on_develop(self) -> None:
        decision = evaluate_git_branch_guard("git status && git commit -m x", self.repo)
        self.assertTrue(decision.is_denied())

    def test_reading_on_develop_is_allowed(self) -> None:
        decision = evaluate_git_branch_guard("git status && git log 2>&1", self.repo)
        self.assertFalse(decision.is_denied())

    def test_creating_a_work_branch_from_develop_is_allowed(self) -> None:
        decision = evaluate_git_branch_guard(
            "git checkout -b userstory/1201-a", str(Path(self.repo))
        )
        self.assertFalse(decision.is_denied())


if __name__ == "__main__":
    unittest.main()
