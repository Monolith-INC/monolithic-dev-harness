"""Every `harness ...` command the skills and references tell the agent to run is one the CLI accepts."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from harness import cli

PLUGIN = Path(__file__).resolve().parents[3]
DOCUMENTS = sorted(
    path
    for folder in ("skills", "references")
    for path in (PLUGIN / folder).rglob("*.md")
    if "vendor" not in path.parts
)
COMMAND = re.compile(r"`(harness (?:[^`|\[\]{}…]|\.\.\.)+?)`")
PLACEHOLDER = re.compile(r"<[^>]*>")
# Phrases the user types in chat for the hook to catch; they are not CLI commands.
TYPED_BY_THE_USER = frozenset({"harness suspend", "harness resume"})


def _commands() -> list[tuple[str, str]]:
    found = []
    for path in DOCUMENTS:
        text = " ".join(path.read_text(encoding="utf-8").split())
        for command in COMMAND.findall(text):
            # A bare name (`harness session`) or a list of choices (`pause/resume`) is prose.
            if (
                "..." in command
                or "/" in command
                or len(command.split()) < 3
                or command.strip() in TYPED_BY_THE_USER
            ):
                continue
            found.append((f"{path.relative_to(PLUGIN)}", command))
    return found


@pytest.mark.parametrize(("where", "command"), _commands())
def test_the_documented_command_parses(where: str, command: str) -> None:
    words = shlex.split(PLACEHOLDER.sub("X", command.replace("<host>", "claude")))[1:]
    try:
        cli.parser().parse_known_args(words)
    except SystemExit as exit_:
        pytest.fail(f"{where}: `{command}` is refused by the CLI (exit {exit_.code})")
