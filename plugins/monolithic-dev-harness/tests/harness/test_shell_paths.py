"""Which paths a shell command writes, as the human-owned and generated-files rules read them.

Reported against 0.7.0-rc.2: read-only inspections of `.harness/state`, and commands that only touch
a scratch folder, were refused as writes to human-owned files. `<repo>` is the project and
`<scratch>` a folder outside it. The refused commands at the end keep their refusals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.harness import shellscan
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
