"""Which paths a shell command writes, as the human-owned and generated-files rules read them.

Reported against 0.7.0-rc.2: read-only inspections of `.harness/state`, and commands that only touch
a scratch folder, were refused as writes to human-owned files. `<repo>` is the project and
`<scratch>` a folder outside it. The refused commands at the end keep their refusals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.harness import inline_python, shellscan
from scripts.harness.rules import (
    make_call,
    shell_human_owned_write,
    shell_writes_human_owned,
    shell_writes_matching,
)

GENERATED = ["**/*.g.dart"]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".harness" / "state" / "work_sessions" / "WS-1").mkdir(parents=True)
    (root / ".harness" / "state" / "host_sessions").mkdir()
    (root / "lib").mkdir()
    return root


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    (tmp_path / "scratch" / "skills" / "cloud").mkdir(parents=True)
    return tmp_path / "scratch"


def spelled(command: str, repo: Path, scratch: Path) -> str:
    return command.replace("<repo>", str(repo)).replace("<scratch>", str(scratch))


def human_owned_write(command: str, repo: Path, scratch: Path) -> str | None:
    text = spelled(command, repo, scratch)
    return shell_human_owned_write(
        make_call("shell", {}, kind="shell", command=text), repo
    )


def generated_write(command: str, repo: Path, scratch: Path) -> str | None:
    text = spelled(command, repo, scratch)
    return shell_writes_matching(
        make_call("shell", {}, kind="shell", command=text), repo, GENERATED
    )


OBSERVED = (
    "cd <scratch> && git -C <scratch> sparse-checkout set skills/cloud/x",
    'S=<scratch>; for d in "$S"/skills/cloud/*; do du -sh "$d"; done',
    "S=<repo>/.harness/state; cat $S/work_sessions/current.json; "
    "for d in $S/work_sessions/WS-*; do ls $d; head -c 400 $d/*.json; done",
)

EXPECTED_ALLOWED = (
    "cd <scratch> && git sparse-checkout set skills/cloud/x",
    'S=<scratch>; find "$S"/skills -type f',
)

LOOPS_AND_CONDITIONS = (
    "for d in <repo>/.harness/state/work_sessions/*; do ls $d; done",
    "for f in .harness/settings.json; do cat $f; done",
    "for f in .harness/settings.json .harness/state; do ls -la $f; done",
    "select f in .harness/settings.json; do cat $f; done",
    "case .harness/settings.json in *.json) echo json;; esac",
    "[[ -f .harness/settings.json ]] && echo yes",
    "if [[ -d .harness/state ]]; then ls .harness/state; fi",
    "cd .harness/state && for d in work_sessions/*; do ls $d; done",
)

ASSIGNMENT_PREFIXES = (
    "FOO=$BAR ls .harness/state",
    'FOO="a b" ls .harness/state',
    "PYTHONPATH=$PWD/lib cat .harness/settings.json",
    "A=1 B=$C head -n 3 .harness/settings.json",
)

STILL_REFUSED = (
    "echo x > .harness/settings.json",
    "S=.harness/state; echo x > $S/approvals/HB-1.json",
    "cd <repo>/.harness/state && echo x > decision.json",
    "cd <repo>/.harness/state/approvals && rm -f HB-1.json",
    "for f in .harness/settings.json; do echo x > $f; done",
    "for f in a b; do cp /tmp/p .harness/settings.json; done",
    "S=.harness/state; for f in $S/approvals/*; do rm $f; done",
    "for f in .harness/settings.json; do sed -i s/a/b/ $f; done",
    "select f in a; do cp /tmp/p .harness/settings.json; done",
    "case x in *) rm .harness/settings.json;; esac",
    "[[ -f x ]] && rm .harness/settings.json",
    "FOO=$BAR cp /tmp/p .harness/settings.json",
    'FOO="a b" tee .harness/settings.json',
    "A=1 B=$C sh -c 'cp /tmp/p .harness/settings.json'",
    "cd <scratch>; cp x .harness/settings.json",
)


@pytest.mark.parametrize("command", (*OBSERVED, *EXPECTED_ALLOWED))
def test_the_reported_commands_are_not_refused(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is None


@pytest.mark.parametrize("command", LOOPS_AND_CONDITIONS)
def test_the_header_of_a_loop_or_a_condition_is_not_a_write(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is None


@pytest.mark.parametrize("command", ASSIGNMENT_PREFIXES)
def test_an_assignment_in_front_of_a_reader_is_not_a_write(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is None


@pytest.mark.parametrize("command", STILL_REFUSED)
def test_writes_to_human_owned_files_are_still_refused(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is not None


@pytest.mark.parametrize(
    "command",
    (
        "for f in lib/a.g.dart; do cat $f; done",
        "[[ -f lib/a.g.dart ]] && wc -l lib/a.g.dart",
        "case lib/a.g.dart in *) echo generated;; esac",
        "FOO=$BAR grep -n x lib/a.g.dart",
    ),
)
def test_generated_files_are_not_written_by_reading_them(
    command: str, repo: Path, scratch: Path
) -> None:
    assert generated_write(command, repo, scratch) is None


@pytest.mark.parametrize(
    "command",
    (
        "for f in lib/a.g.dart; do echo x > $f; done",
        "FOO=$BAR cp /tmp/a lib/a.g.dart",
        "[[ -f x ]] && rm lib/a.g.dart",
    ),
)
def test_generated_files_are_still_protected(
    command: str, repo: Path, scratch: Path
) -> None:
    assert generated_write(command, repo, scratch) is not None


def test_an_unexpanded_variable_keeps_its_name_in_a_path(repo: Path) -> None:
    writes = shellscan.scan('cp a "$S"/skills')
    assert writes.targets == ("$S/skills",)
    assert not shell_writes_human_owned('cp a "$S"/skills', repo)


def test_a_variable_assigned_in_the_same_command_is_followed(
    repo: Path, scratch: Path
) -> None:
    assert shell_writes_human_owned("S=.harness/state; cp a $S/approvals/x", repo)
    assert not shell_writes_human_owned(f"S={scratch}; cp a $S/approvals/x", repo)


OUTSIDE_THE_REPOSITORY = (
    "cd <scratch> && python3 -c \"open('.harness/settings.json', 'w')\"",
    "cd <scratch> && sh run.sh .harness/settings.json",
    "python3 <scratch>/build.py <scratch>/.harness/settings.json",
    "S=<scratch>; python3 build.py $S/.harness/state",
)

INSIDE_THE_REPOSITORY = (
    "cd <repo> && python3 -c \"open('.harness/settings.json', 'w')\"",
    "cd <repo>/lib && python3 -c \"open('../.harness/settings.json', 'w')\"",
    "cd <repo>/.harness/state && python3 -c \"open('decision.json', 'w')\"",
    "cd <scratch>; python3 -c \"open('.harness/settings.json', 'w')\"",
    "python3 build.py <repo>/.harness/settings.json",
    "python3 build.py ~/.harness/settings.json",
)


@pytest.mark.parametrize("command", OUTSIDE_THE_REPOSITORY)
def test_code_that_runs_outside_the_repository_is_not_refused(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is None


@pytest.mark.parametrize("command", INSIDE_THE_REPOSITORY)
def test_code_that_could_write_inside_the_repository_is_refused(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is not None


def test_the_refusal_names_a_human_owned_file_not_a_word_of_the_code(
    repo: Path, scratch: Path
) -> None:
    command = "cd <repo>/.harness/state && python3 -c \"open('decision.json', 'w')\""
    assert human_owned_write(command, repo, scratch) == ".harness/state/decision.json"


@pytest.mark.parametrize(
    "command",
    (
        "cd <scratch> && echo x > lib/a.g.dart",
        "cd <scratch> && sh gen.sh lib/a.g.dart",
        "sh gen.sh <scratch>/lib/a.g.dart",
    ),
)
def test_generated_files_outside_the_repository_are_not_protected(
    command: str, repo: Path, scratch: Path
) -> None:
    assert generated_write(command, repo, scratch) is None


@pytest.mark.parametrize(
    "command",
    (
        "cd <repo> && echo x > lib/a.g.dart",
        "cd <repo>/lib && sh gen.sh a.g.dart",
        "sh gen.sh <repo>/lib/a.g.dart",
        "cd <scratch>; sh gen.sh lib/a.g.dart",
    ),
)
def test_generated_files_in_the_repository_stay_protected(
    command: str, repo: Path, scratch: Path
) -> None:
    assert generated_write(command, repo, scratch) is not None


READ_ONLY_PYTHON = (
    "import json; print(json.load(open('decision-history.json')))",
    "import json, sys; print(json.load(sys.stdin))",
    "import glob, os; print(sorted(os.listdir('.')), glob.glob('*/*.json'))",
    "from pathlib import Path; print(Path('x.json').read_text())",
    "import sys; print(open(sys.argv[1], 'rb').read())",
    "with open('x', mode='r', encoding='utf-8') as f: print(f.read())",
    "import re; print([m for m in re.findall(r'WS-\\d+', open('x').read())])",
)

WRITING_PYTHON = (
    "open('x', 'w')",
    "open('x', 'a')",
    "open('x', mode='w')",
    "open('x', 'r+')",
    "open('x', mode)",
    "open(*args)",
    "open('x', **options)",
    "import os; os.remove('x')",
    "import os; os.system('rm x')",
    "import os; os.popen('rm x')",
    "import subprocess",
    "import shutil",
    "from os import system as run",
    "from os import *",
    "from . import sibling",
    "__import__('os').system('rm x')",
    "eval('1')",
    "exec('1')",
    "import os; getattr(os, 'sys' + 'tem')('rm x')",
    "from pathlib import Path; Path('x').write_text('y')",
    "from pathlib import Path; Path('x').touch()",
    "import sys; sys.stdout.write('x')",
    "import numpy",
    "import operator",
    "import typing",
    "import functools",
    "import os; os.posix_spawn('/bin/rm', ['rm', 'x'], {})",
    "import os; os.setxattr('x', 'user.a', b'b')",
    "print(",
    "print('$HOME')",
    "print('`id`')",
)

PROGRAM_SOURCES = (
    (("-c", "print(1)"), "", True),
    (("-u", "-c", "print(1)", "a", "b"), "", True),
    (("-",), "print(1)", True),
    ((), "print(1)", True),
    (("-c",), "", False),
    (("-",), "", False),
    (("tool.py", "-c", "print(1)"), "", False),
    (("-Ic", "print(1)"), "", False),
    (("-m", "pytest"), "print(1)", False),
    (("-W", "ignore", "-c", "print(1)"), "", False),
)


@pytest.mark.parametrize("code", READ_ONLY_PYTHON)
def test_python_that_only_reads_is_read_only(code: str) -> None:
    assert inline_python.reads_only("python3", ("-c", code), "")


@pytest.mark.parametrize("code", WRITING_PYTHON)
def test_python_that_could_write_is_not_read_only(code: str) -> None:
    assert not inline_python.reads_only("python3", ("-c", code), "")


@pytest.mark.parametrize(("args", "stdin", "expected"), PROGRAM_SOURCES)
def test_only_a_program_given_up_front_is_read(
    args: tuple[str, ...], stdin: str, expected: bool
) -> None:
    assert inline_python.reads_only("python3", args, stdin) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    (("python", True), ("python3", True), ("python3.12", True), ("node", False)),
)
def test_only_python_is_read(name: str, expected: bool) -> None:
    assert inline_python.reads_only(name, ("-c", "print(1)"), "") is expected


PYTHON_READS = (
    "cd <repo>/.harness/state && ls host_sessions work_sessions; "
    "grep -l decision work_sessions/*; "
    "python3 -c \"import json; print(json.load(open('decision-history.json')))\"",
    "python3 -c \"import json; print(json.load(open('<repo>/.harness/state/decision-history.json')))\"",
    "cd <repo>/.harness/state && python3 - <<'EOF'\n"
    "import json\nprint(json.load(open('decision-history.json')))\nEOF",
    "cat <repo>/.harness/settings.json | python3 -c 'import json,sys; print(json.load(sys.stdin))'",
    'python3 -c "import sys; print(open(sys.argv[1]).read())" .harness/settings.json',
    "timeout 5 python3.12 -c \"print(open('.harness/settings.json', 'rb').read())\"",
)

PYTHON_WRITES = (
    "cd <repo>/.harness/state && python3 -c \"open('decision.json', 'w').write('{}')\"",
    "python3 -c \"import os; os.remove('.harness/settings.json')\"",
    "python3 -c \"from pathlib import Path; Path('.harness/settings.json').write_text('{}')\"",
    "python3 -c \"import shutil; shutil.copy('x', '.harness/settings.json')\"",
    "python3 -c \"exec(open('.harness/settings.json').read())\"",
    "python3 - <<'EOF'\nopen('.harness/settings.json', 'w')\nEOF",
    'python3 -c "$CODE" .harness/settings.json',
    "python3 tool.py .harness/settings.json",
    'python3 tool.py -c "print(1)" .harness/settings.json',
    "python3 -Ic \"open('.harness/settings.json', 'w')\"",
    "node -e \"require('fs').writeFileSync('.harness/settings.json', '{}')\"",
    'python3 -c "print(1)" > .harness/settings.json',
)


@pytest.mark.parametrize("command", PYTHON_READS)
def test_python_that_only_reads_is_not_a_write(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is None


@pytest.mark.parametrize("command", PYTHON_WRITES)
def test_python_that_could_write_a_human_owned_file_is_refused(
    command: str, repo: Path, scratch: Path
) -> None:
    assert human_owned_write(command, repo, scratch) is not None


def test_generated_files_are_read_and_written_by_python_alike(
    repo: Path, scratch: Path
) -> None:
    read = "python3 -c \"print(open('lib/a.g.dart').read())\""
    write = "python3 -c \"open('lib/a.g.dart', 'w')\""
    assert generated_write(read, repo, scratch) is None
    assert generated_write(write, repo, scratch) == "lib/a.g.dart"
