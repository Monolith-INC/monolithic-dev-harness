"""The workflow policy reads commands through the shared reader, like the harness rules."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.hook_runtime import _is_mutating_git
from scripts import hook_runtime
from scripts.policy import CanonicalToolEvent
from scripts.policy.commands import is_code, writes_code
from scripts.policy.git_branch_guard import evaluate_git_branch_guard


class WritesCodeTests(unittest.TestCase):
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
                    self.assertFalse(writes_code(command, tmp, None))

    def test_writing_into_the_repository_is(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for command in (
                "echo x > notes.md",
                "cp /tmp/a lib/a.dart",
                "sed -i s/a/b/ lib/a.dart",
                f"echo x > {tmp}/notes.md",
            ):
                with self.subTest(command=command):
                    self.assertTrue(writes_code(command, tmp, None))


CODE = ["projects/app/lib/**/*.dart", "projects/app/test/**/*_test.dart"]


class SpecBeforeCodeCoversCodeOnlyTests(unittest.TestCase):
    """Reported from a real session: setting the repository up was refused for want of a spec."""

    def test_setup_files_are_not_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for command in (
                "git checkout -- .gitignore && printf '.harness/state/\\n' >> .git/info/exclude",
                "echo x > AI_Codex/Checkpoints/build.md",
                "echo '{}' > .harness/review/sources.json",
                "python3 scripts/tool.py --out notes.md",
                f"echo x > {tmp}/README.md",
            ):
                with self.subTest(command=command):
                    self.assertFalse(writes_code(command, tmp, CODE))

    def test_code_and_tests_are(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for command in (
                "echo x > projects/app/lib/a.dart",
                "sed -i s/a/b/ projects/app/test/a_test.dart",
                "cd projects/app && echo x > lib/main.dart",
                "rm -rf projects/app",
                "git checkout -- projects",
                "python3 -c 'open(\"x\")' projects/app/lib/a.dart",
                f"echo x > {tmp}/projects/app/lib/b.dart",
            ):
                with self.subTest(command=command):
                    self.assertTrue(writes_code(command, tmp, CODE))

    def test_without_code_globs_every_file_but_gits_and_the_harnesss_is_code(self) -> None:
        self.assertTrue(is_code("README.md", None))
        self.assertFalse(is_code(".git/info/exclude", None))
        self.assertFalse(is_code(".harness/state/x.json", None))
        self.assertFalse(is_code("../elsewhere/a.dart", None))

    def test_editing_a_file_asks_only_for_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness").mkdir()
            (root / ".harness/policy.json").write_text(
                '{"schemaVersion": 1, "tests_required": [{"source": ["lib/**"], "tests": ["test/**"]}]}'
            )

            def edits_code(path: str | None) -> bool:
                return hook_runtime._edits_code(
                    CanonicalToolEvent(
                        client="claude", tool_name="Write", file_path=path, workspace_root=tmp
                    )
                )

            self.assertTrue(edits_code(f"{tmp}/lib/a.dart"))
            self.assertTrue(edits_code("test/a_test.dart"))
            self.assertTrue(edits_code(None))
            self.assertFalse(edits_code(f"{tmp}/.gitignore"))
            self.assertFalse(edits_code(f"{tmp}/AI_Codex/Checkpoints/build.md"))
            self.assertFalse(edits_code("/tmp/elsewhere/lib/a.dart"))


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
