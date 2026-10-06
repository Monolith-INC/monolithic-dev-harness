"""Recognise a shell command that is exactly one run of this plugin's `harness` CLI.

The hooks give a few `harness` commands special treatment (reading a pending decision, choosing a
work session). Text that merely mentions them must not count, and nothing may ride along: a
command with any shell operator, substitution, or redirection is not a harness invocation.
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
# Anything a shell would act on beyond running one program with arguments.
_SHELL_SYNTAX = frozenset(";&|<>()`$\n\r")


def harness_args(command: str, cwd: Path) -> tuple[str, ...] | None:
    """The arguments after `harness` when `command` is exactly one harness run, else None."""
    if any(character in _SHELL_SYNTAX for character in command):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    match words:
        case [executable, *args] if this_harness(executable, cwd):
            return tuple(args)
        case _:
            return None


def this_harness(executable: str, cwd: Path) -> bool:
    """This plugin's `bin/harness`, or the `harness` the installer linked onto the path."""
    found = shutil.which(executable) if "/" not in executable else str(cwd / executable)
    if found is None or not Path(found).is_file():
        return False
    resolved = Path(found).resolve()
    linked = shutil.which("harness")
    return resolved == (PLUGIN_ROOT / "bin/harness").resolve() or (
        linked is not None
        and resolved == Path(linked).resolve()
        and (resolved.parents[1] / "scripts/harness/cli.py").is_file()
    )


def option(args: tuple[str, ...], name: str) -> str | None:
    """The value of `--name value` or `--name=value`, if given once."""
    values = [
        args[index + 1] if word == name else word.split("=", 1)[1]
        for index, word in enumerate(args)
        if (word == name and index + 1 < len(args)) or word.startswith(name + "=")
    ]
    return values[0] if len(values) == 1 else None
