"""Remove non-expanding heredoc data from the shell substitution search only.

The invocation parser still receives the original command, including executable shell stdin.
Unknown or malformed headers remain unmasked so this helper cannot hide executable text.
"""

from __future__ import annotations

import re
import shlex
from itertools import accumulate, islice, takewhile

from core.result import Err, Ok, attempt

_TOKENS = re.compile(
    r"""<<-?|[;&|()]|(?:'[^']*'|"(?:\\.|[^"\\])*"|\\.|[^\s<>;&|()'"\\])+|[<>]+"""
)


def _delimiter(raw: str, tabs: bool) -> tuple[str, bool, bool] | None:
    match re.fullmatch(r'''[A-Za-z0-9_.-]+|'[^'\r\n]*'|"[^"$`\\\r\n]*"''', raw):
        case None:
            return None  # shell expansions and mixed quoting remain fully guarded
        case _:
            pass
    match attempt(
        lambda: shlex.split(raw), "shell_word", "heredoc delimiter", ValueError
    ):
        case Ok([name]) if name:
            return name, any(char in raw for char in "'\"\\"), tabs
        case Err() | _:
            return None


def _delimiters(line: str) -> tuple[tuple[str, bool, bool], ...]:
    match "((" in line:
        case True:
            return (("\0", False, False),)  # ambiguous headers stay unmasked
        case _:
            pass
    match tuple(
        takewhile(
            lambda token: not token.group().startswith("#"), _TOKENS.finditer(line)
        )
    ):
        case tokens:
            return _validated(
                tuple(
                    _delimiter(tokens[index + 1].group(), token.group() == "<<-")
                    if tokens[index + 1].end() == len(line)
                    or line[tokens[index + 1].end()] in " \t\n;<>&|"
                    else None
                    for index, token in enumerate(tokens[:-1])
                    if token.group() in {"<<", "<<-"}
                )
            )


def _validated(
    delimiters: tuple[tuple[str, bool, bool] | None, ...],
) -> tuple[tuple[str, bool, bool], ...]:
    match any(delimiter is None for delimiter in delimiters):
        case True:
            return (
                ("\0", False, False),
            )  # ambiguous bodies stay unmasked to end of input
        case False:
            return tuple(delimiter for delimiter in delimiters if delimiter is not None)


def _line(
    state: tuple[tuple[tuple[str, bool, bool], ...], str], line: str
) -> tuple[tuple[tuple[str, bool, bool], ...], str]:
    match state[0]:
        case ((name, quoted, tabs), *remaining):
            match (
                line.lstrip("\t").removesuffix("\n")
                if tabs
                else line.removesuffix("\n")
            ):
                case found if found == name:
                    return tuple(remaining), line
                case _:
                    return state[0], "".join(
                        "\n" if char == "\n" else " " for char in line
                    ) if quoted else line
        case _:
            return _delimiters(line), line


def expansion_source(command: str) -> str:
    match "<<" in command:
        case False:
            return command
        case True:
            return "".join(
                item[1]
                for item in islice(
                    accumulate(
                        re.findall(r"[^\n]*\n|[^\n]+$", command),
                        _line,
                        initial=((), ""),
                    ),
                    1,
                    None,
                )
            )
