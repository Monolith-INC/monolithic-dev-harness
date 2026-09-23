"""What a shell command would write.

The rules need one question answered about a `Bash` call: which paths could this command write?
Reading a protected file is fine; writing it is not. Answering that with a regex fails in both
directions — `2>/dev/null` looks like a write, and `sudo tee x` does not look like one — so this
module tokenizes the command instead.

`scan` returns the write targets it can name, plus `opaque` when the command carries a write vector
it cannot follow (`eval`, `sh -c`, `xargs`, an interpreter running inline code, a parse failure).
Callers treat `opaque` as "assume it writes whatever it names": fail closed, never open.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath

# Commands that only read. Anything not listed is treated as a writer when it names a watched path.
READERS = frozenset(
    {
        "cat",
        "cmp",
        "diff",
        "du",
        "echo",
        "file",
        "git",
        "grep",
        "head",
        "jq",
        "less",
        "ls",
        "md5sum",
        "more",
        "printf",
        "pwd",
        "rg",
        "sha1sum",
        "sha256sum",
        "shasum",
        "shellcheck",
        "sort",
        "stat",
        "tail",
        "test",
        "uniq",
        "wc",
        "which",
        "yq",
    }
)
# Readers that become writers with a flag.
CONDITIONAL_READERS = {
    "sed": re.compile(r"^(-[a-zA-Z]*i|--in-place)"),
    "awk": re.compile(r"^(-i|--in-place)"),
    "find": re.compile(r"^-(delete|exec|execdir|ok|okdir|fprint|fprintf|fls)$"),
    "python": re.compile(r"^(-c|-)$"),
    "python3": re.compile(r"^(-c|-)$"),
    "node": re.compile(r"^(-e|-p|--eval)$"),
    "perl": re.compile(r"^-[a-zA-Z]*[ei]"),
    "ruby": re.compile(r"^-e$"),
}
# Interpreters and dispatchers whose real command this module cannot see.
OPAQUE = frozenset(
    {
        "bash",
        "dash",
        "eval",
        "exec",
        "ksh",
        "node",
        "perl",
        "python",
        "python3",
        "ruby",
        "sh",
        "source",
        "xargs",
        "zsh",
        ".",
    }
)
# `<interpreter> -m <module>` invocations that only read.
READER_MODULES = frozenset({"json.tool"})
# Wrappers that run the command that follows them.
WRAPPERS = frozenset(
    {"command", "env", "nice", "nohup", "stdbuf", "sudo", "time", "timeout"}
)
REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>", ">&"})
_SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "(", ")", "{", "}", "\n"})
# Shell keywords that start a new simple command inside a compound one.
_KEYWORDS = frozenset(
    {"do", "done", "then", "else", "elif", "fi", "esac", "in", "!", "time"}
)
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SUBSTITUTION = ("$", "`")


@dataclass(frozen=True)
class ShellWrites:
    targets: tuple[str, ...]
    opaque: bool


def segments(command: str) -> list[list[str]] | None:
    """The command split into simple commands. None when it cannot be tokenized."""
    result: list[list[str]] = [[]]
    for line in command.splitlines():
        if result[-1]:
            result.append([])
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            return None
        for token in tokens:
            if token in _SEPARATORS or token in _KEYWORDS:
                result.append([])
            else:
                result[-1].append(token)
    return [segment for segment in result if segment]


def _resolve(target: str, cwd: str) -> str:
    if target.startswith(("/", "~")) or not cwd:
        return target
    return PurePosixPath(cwd).joinpath(target).as_posix()


def _is_file_target(token: str) -> bool:
    return bool(token) and not token.startswith(("&", "-"))


def scan(command: str) -> ShellWrites:
    """The paths `command` could write, and whether it hides a write this cannot resolve."""
    parsed = segments(command)
    if parsed is None:
        return ShellWrites((), True)
    targets: list[str] = []
    opaque = False
    cwd = ""
    for segment in parsed:
        words = [token for token in segment if not _ASSIGNMENT.match(token)]
        while words and PurePosixPath(words[0]).name in WRAPPERS:
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[1:]
            if words and PurePosixPath(words[0]).name == "timeout":
                words = words[1:]
        name = PurePosixPath(words[0]).name if words else ""
        arguments = words[1:]

        for index, token in enumerate(segment):
            if token in REDIRECTS and index + 1 < len(segment):
                target = segment[index + 1]
                if target.startswith(_SUBSTITUTION):
                    opaque = True
                elif _is_file_target(target) and target != "/dev/null":
                    targets.append(_resolve(target, cwd))

        if name in {"cd", "pushd"}:
            destination = next((a for a in arguments if not a.startswith("-")), "")
            if destination.startswith(_SUBSTITUTION):
                opaque = True
            cwd = "" if destination in {"", "-", "/"} else _resolve(destination, cwd)
            continue

        if any(token.startswith(_SUBSTITUTION) for token in arguments):
            opaque = True

        writer = name not in READERS
        condition = CONDITIONAL_READERS.get(name)
        if condition is not None:
            writer = any(condition.match(argument) for argument in arguments)
        if name in OPAQUE:
            module = (
                arguments[1] if arguments[:1] == ["-m"] and len(arguments) > 1 else ""
            )
            if module in READER_MODULES:
                writer = False
            else:
                opaque = True
                writer = True
        if writer:
            targets.extend(
                _resolve(argument, cwd)
                for argument in arguments
                if _is_file_target(argument)
            )
            if not arguments and cwd:
                targets.append(cwd)
    return ShellWrites(tuple(targets), opaque)
