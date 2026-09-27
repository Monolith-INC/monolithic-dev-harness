"""What a shell command runs and writes, as the rules see it.

The hook tests drive the rules end to end; these pin the analyzer underneath them, including every
bypass and false refusal a review found, so a regression shows up here and not in production.
"""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.harness import shellscan
from scripts.harness.rules import (
    is_remote_write,
    make_call,
    shell_human_owned_write,
    shell_writes_human_owned,
    shell_writes_matching,
)
from scripts.harness.tracker_policy import TrackerPolicy

# Reading human-owned files is always fine, whatever else is on the line.
HUMAN_OWNED_READS = (
    "cat .harness/settings.json 2>/dev/null | head",
    "cd .harness && cat settings.json 2>&1 | head",
    "cd .harness && ls -la > /tmp/listing",
    "jq .azure .harness/settings.json > /tmp/azure.json",
    "python3 -m json.tool .harness/state/approvals/HB-7Q2K.json",
    "cat .harness/settings.json | python3 -c 'import json,sys; print(json.load(sys.stdin))'",
    "git diff .harness/settings.json",
    "cp .harness/settings.json /tmp/backup.json",
    # Wrappers run the command after them; `timeout`'s duration is not the command.
    "timeout 60 cat .harness/settings.json",
    "nice -n 5 cat .harness/settings.json",
    "sudo cat .harness/settings.json",
    # Readers beyond the usual few.
    "shasum .harness/settings.json",
    "shellcheck .harness/settings.json",
    "bat .harness/settings.json",
    "realpath .harness/settings.json",
    "tar -tf safe.tar -C .harness",
    # A subshell's `cd` ends with the subshell.
    "(cd .harness/state/approvals && ls); echo hi > notes.txt",
    # A heredoc body is data for `cat`, not commands.
    "cat >> docs/harness.md <<'EOF'\ncp .harness/settings.json /tmp/b.json\nEOF",
    "cp /tmp/p.json \\\n  lib/x.json",
    # Harmless writes near human-owned files.
    "mkdir -p .harness/state",
    "echo x > .harness/state/checks/abc.json",
    "python3 scripts/harness/checks.py --staged",
    "find . -name '*.tmp' -delete",
    "git apply ok.patch",
    "tar -xf safe.tar",
    # `$((1<<2))` is arithmetic, not a heredoc; a `#` inside a word is not a comment.
    "echo $((1<<2))\ncat .harness/settings.json",
    "echo a#b; cat .harness/settings.json",
    # `find -name` with a non-json extension cannot select a record.
    "find .harness -name '*.tmp' -delete",
)

HUMAN_OWNED_WRITES = (
    "echo x > .harness/settings.json",
    "echo x > .harness/*.json",
    "sed -i s/4007// .harness/settings.json",
    "yq -i '.x=1' .harness/settings.json",
    "sort -o .harness/settings.json /tmp/x",
    "dd if=/tmp/evil of=.harness/settings.json",
    # A second line is a second command.
    "echo hi\ncp /tmp/p.json .harness/settings.json",
    "cd .harness\necho {} > settings.json",
    "ls\ntee .harness/settings.json < /tmp/p",
    # Wrappers, dispatchers, and compound commands run the writer all the same.
    "env X=1 cp /tmp/p.json .harness/settings.json",
    "sudo tee .harness/settings.json",
    "timeout 5 sh -c 'cp /tmp/p.json .harness/settings.json'",
    "nice -n 5 sh -c 'cp /tmp/p .harness/settings.json'",
    "timeout --preserve-status 5 bash -c 'rm .harness/settings.json'",
    "sudo timeout 5 sh -c 'rm .harness/settings.json'",
    "echo .harness/settings.json | xargs rm",
    "eval 'cp /tmp/p .harness/settings.json'",
    "for f in a; do cp $f .harness/settings.json; done",
    "if true; then cp /tmp/p .harness/settings.json; fi",
    "(cd .harness && rm settings.json)",
    "bash <<EOF\ncp /tmp/p .harness/settings.json\nEOF",
    "python3 -c \"open('.harness/settings.json','w')\"",
    "python3 - <<EOF\nopen('.harness/settings.json','w')\nEOF",
    # A path held in a variable could be any path on the line.
    "P=.harness/settings.json; echo x > $P",
    # `..` does not hide a target, including out of the agent-writable checks directory.
    "cp /tmp/evil.json .harness/../.harness/settings.json",
    "cp /tmp/evil.json .harness/state/../settings.json",
    "tee .harness/../.harness/state/approvals/HB-XXXX.json",
    "mv /tmp/a.json .harness/state/checks/../approvals/HB-1.json",
    # A directory target lands on the policy as well as naming it does.
    "cp /tmp/policy.json .harness/",
    "cp /tmp/p.json --target-directory=.harness",
    "rsync -a /tmp/h/ .harness/",
    "tar -xf p.tar -C .harness",
    "tar -xf p.tar --directory=.harness",
    "unzip -o p.zip -d .harness",
    "ln -s .harness /tmp/h",
    "find .harness -name settings.json -delete",
    # Removing everything removes the policy too.
    "rm -rf .",
    "rm -rf .[!.]*",
    "git clean -fdx",
    "git stash -u",
    # Git and archives write what they carry.
    "git checkout other -- .harness/settings.json",
    "git apply p.patch",
    "tar -xf evil.tar",
    # Third review: file-descriptor redirects, failed or unknown `cd`, `..` out and back in.
    "cp x .harness/settings.json 2>/dev/null",
    "cp x .harness/settings.json 2>&1",
    "cd no_such_dir; rm -rf .harness",
    "cd /nonexistent; cp x .harness/settings.json",
    "true | cd /tmp; cp x .harness/settings.json",
    "D=.harness; cd $D && cp x settings.json",
    "cp x ../repo/.harness/settings.json",
    "echo {} 1<>.harness/settings.json",
    "cp evil .harness/$F",
    # Substitutions run too.
    'echo "$(cp x .harness/settings.json)"',
    "echo `rm .harness/settings.json`",
    "x=$(rm .harness/settings.json)",
    "diff <(cp x .harness/settings.json) y",
    "sh -c -- 'cp x .harness/settings.json'",
    "env -S 'cp x .harness/settings.json'",
    "cd .harness && python3 -c \"open('settings.json','w')\"",
    # Readers that write when given a second operand or an output option.
    "uniq x .harness/settings.json",
    "xxd -r dump .harness/settings.json",
    "tree -o .harness/settings.json",
    # Patches and git that write through a directory, a prefix, or a missing file.
    "git apply --directory=.harness ok.patch",
    "git apply missing.patch",
    "cat p.patch | git apply",
    "git checkout HEAD -- .",
    "git restore --source=main .",
    # `find` patterns that can select a record.
    "find .harness/state/approvals -name 'HB-?????.json' -exec sed -i s/a/b/ {} +",
    "find . -iname POLICY.JSON -delete",
)

REMOTE_WRITES = (
    "git push",
    "sudo git push",
    "env X=1 git push",
    "timeout 60 git push",
    "(git push)",
    "if true; then git push; fi",
    "echo x | xargs git push",
    "bash -c 'git push origin HEAD'",
    "time -p git push",
    "/usr/bin/time git push",
    "{ git push; }",
    "echo `git push`",
    "echo $(git push)",
    "exec git push",
    "echo a#b; git push",
    "echo $((1<<2))\ngit push",
    # An unbalanced quote still shows the push after it.
    "git commit -m 'oops && git push",
)


class ShellscanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / "p.patch").write_text(
            "--- a/.harness/settings.json\n+++ b/.harness/settings.json\n@@\n"
        )
        (self.repo / "ok.patch").write_text("--- a/lib/a.dart\n+++ b/lib/a.dart\n@@\n")
        self._tar("safe.tar", "lib/x.txt")
        self._tar("evil.tar", ".harness/settings.json")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _tar(self, name: str, member: str) -> None:
        with tarfile.open(self.repo / name, "w") as archive:
            info = tarfile.TarInfo(member)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))


class HumanOwnedTests(ShellscanTestCase):
    def test_reads_are_allowed(self) -> None:
        for command in HUMAN_OWNED_READS:
            with self.subTest(command=command):
                self.assertFalse(shell_writes_human_owned(command, self.repo))

    def test_writes_are_caught(self) -> None:
        for command in HUMAN_OWNED_WRITES:
            with self.subTest(command=command):
                self.assertTrue(shell_writes_human_owned(command, self.repo))

    def test_relative_paths_start_where_the_shell_runs(self) -> None:
        (self.repo / "projects" / "app").mkdir(parents=True)
        call = make_call(
            "Bash",
            {"command": "cp /tmp/p ../../.harness/settings.json"},
            cwd=str(self.repo / "projects" / "app"),
        )
        self.assertEqual(
            shell_human_owned_write(call, self.repo), ".harness/settings.json"
        )


NO_TRACKERS = TrackerPolicy((), (), (), frozenset(), "")


class RemoteWriteTests(unittest.TestCase):
    def test_every_way_of_running_git_push_is_a_remote_write(self) -> None:
        for command in REMOTE_WRITES:
            with self.subTest(command=command):
                self.assertTrue(
                    is_remote_write(
                        make_call("Bash", {"command": command}), NO_TRACKERS
                    )
                )

    def test_other_git_commands_are_not(self) -> None:
        for command in ("git status", "git log --oneline", "echo git push"):
            with self.subTest(command=command):
                self.assertFalse(
                    is_remote_write(
                        make_call("Bash", {"command": command}), NO_TRACKERS
                    )
                )


class GeneratedFileTests(unittest.TestCase):
    def _written(self, command: str) -> str | None:
        return shell_writes_matching(
            make_call("Bash", {"command": command}), Path("."), ["**/*.g.dart"]
        )

    def test_reads_are_allowed(self) -> None:
        for command in (
            "grep -rn --include=*.g.dart foo lib 2>/dev/null",
            "timeout 30 cat lib/a.g.dart",
            "find . -name '*.g.dart' -exec grep -l foo {} \\;",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self._written(command))

    def test_writes_are_caught_including_unresolved_ones(self) -> None:
        for command in (
            "eval 'cp /tmp/a lib/a.g.dart'",
            "sh -c 'echo x > lib/a.g.dart'",
            "dd if=/tmp/x of=lib/a.g.dart",
            "yq -i '.a=1' lib/a.g.dart",
        ):
            with self.subTest(command=command):
                self.assertEqual(self._written(command), "lib/a.g.dart")


class InvocationTests(unittest.TestCase):
    def test_wrappers_are_unwrapped_to_the_real_command(self) -> None:
        for command, name, args in (
            ("timeout 5 cp a b", "cp", ("a", "b")),
            ("timeout -s KILL 5 cp a b", "cp", ("a", "b")),
            ("nice -n 5 cp a b", "cp", ("a", "b")),
            ("env X=1 Y=2 cp a b", "cp", ("a", "b")),
            ("sudo -u root cp a b", "cp", ("a", "b")),
        ):
            with self.subTest(command=command):
                (invocation,) = shellscan.invocations(command)
                self.assertEqual((invocation.name, invocation.args), (name, args))

    def test_cd_is_scoped_to_its_subshell(self) -> None:
        found = shellscan.invocations("(cd lib && ls); ls")
        self.assertEqual([i.cwd for i in found if i.name == "ls"], ["lib", ""])

    def test_a_cd_into_a_variable_leaves_the_directory_unknown(self) -> None:
        writes = shellscan.scan('cd "$DIR" && echo x > settings.json')
        self.assertIn("settings.json", writes.unresolved)


if __name__ == "__main__":
    unittest.main()
