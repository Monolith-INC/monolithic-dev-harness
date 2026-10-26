"""Inline interpreter code: prose wildcards are not `.harness` targets, real globs still are."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.rules import shell_writes_human_owned

PROSE = (
    # Seen in a Claude acceptance run: Markdown bold in a heredoc edit of a plan file.
    "python3 - <<'EOF'\n"
    "p='docs/backlog/approach.md'\n"
    "s=open(p).read().replace(\n"
    '"**A. Save tasks on the device (becomes a new persistence feature, not a bug fix).**",\n'
    '"**A. Save tasks on the device. Not pursued.**")\n'
    "open(p,'w').write(s)\n"
    "EOF",
    "python3 -c \"print('Done.** Next.*')\"",
)

TARGETS = (
    "python3 - <<EOF\nimport glob, os\n[os.remove(f) for f in glob.glob('.h*/settings.json')]\nEOF",
    "python3 - <<EOF\nopen('.harness/settings.json','w')\nEOF",
)


@pytest.mark.parametrize("command", PROSE)
def test_prose_wildcards_in_inline_code_are_not_harness_writes(
    tmp_path: Path, command: str
) -> None:
    assert not shell_writes_human_owned(command, tmp_path)


@pytest.mark.parametrize("command", TARGETS)
def test_globs_that_spell_the_harness_folder_still_count(
    tmp_path: Path, command: str
) -> None:
    assert shell_writes_human_owned(command, tmp_path)
