from __future__ import annotations

import re
import shlex

_DEV_NULL_TARGETS = frozenset({"/dev/null", "/dev/stderr", "/dev/stdout"})


def extract_shell_write_targets(command: str) -> list[str]:
    """Return filesystem paths a shell command would create or overwrite."""
    if not command or not command.strip():
        return []

    targets: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        cleaned = raw.strip().strip("'\"")
        if not cleaned or cleaned in _DEV_NULL_TARGETS or cleaned in seen:
            return
        if cleaned.startswith("&"):
            return
        seen.add(cleaned)
        targets.append(cleaned)

    for match in re.finditer(r"(?:^|[\s|;&])(?:\d+|&)?>{1,2}\s*(\S+)", command):
        add(match.group(1))

    for match in re.finditer(r"\btee\b(?:\s+-a)?\s+(\S+)", command):
        add(match.group(1))

    for match in re.finditer(r"\bsed\b[^|;&]*?-i(?:\s+\S+)?\s+(\S+)", command):
        add(match.group(1))

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return targets

    cmd = tokens[0].rsplit("/", 1)[-1]
    if (
        cmd in {"cp", "mv", "install", "touch", "truncate"}
        and len(tokens) >= 2
        and "Tickets/" not in command
    ):
        add(tokens[-1])

    if cmd == "dd":
        for token in tokens[1:]:
            if token.startswith("of="):
                add(token[3:])

    return targets
