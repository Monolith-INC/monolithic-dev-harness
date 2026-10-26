"""Whether inline Python only reads.

`python3 -c '…'` and `python3 - <<EOF` write whatever their code writes, so the scanner cannot follow
them. Code that imports only modules that read, never names anything that writes or runs another
program, and opens files only for reading writes nothing, whatever paths it names. Code that does not
parse, takes part of itself from a shell variable, or is not given on the command line or stdin is not
provably read-only.
"""

from __future__ import annotations

import ast
import re

from core.result import Ok, attempt

PYTHON = re.compile(r"^python[0-9.]*$")

# Modules whose use cannot write once the names below are refused.
READERS = frozenset(
    {
        *("base64", "collections", "csv", "datetime", "difflib", "fnmatch", "glob"),
        *("hashlib", "io", "itertools", "json", "math", "os", "pathlib", "pprint"),
        *("re", "shlex", "statistics", "string", "sys", "textwrap", "time", "tomllib"),
    }
)
# Names (called or only mentioned) that write, run another program, or reach one indirectly.
CAPABLE = frozenset(
    {
        *("breakpoint", "chmod", "chown", "compile", "delattr", "eval", "exec"),
        *("fdopen", "FileIO", "forkpty", "ftruncate", "getattr", "globals"),
        *("hardlink_to", "lchmod", "lchown", "link", "locals", "makedirs", "mkdir"),
        *("mkfifo", "mknod", "modules", "open", "popen", "remove", "removedirs"),
        *("removexattr", "rename", "renames", "replace", "rmdir", "rmtree", "sendfile"),
        *("setattr", "setxattr", "symlink", "symlink_to", "system", "touch"),
        *("truncate", "unlink", "urlretrieve", "utime", "vars"),
    }
)
_CAPABLE_PREFIXES = ("__", "exec", "spawn", "posix_spawn", "write", "pwrite")
_WRITING_MODE = frozenset("wax+")
_SHELL_MARKS = ("$", "`")


def reads_only(name: str, args: tuple[str, ...], stdin_text: str) -> bool:
    """Whether the command `name args…` (with `stdin_text` on its stdin) is Python that only reads."""
    code = _program(args, stdin_text) if PYTHON.match(name) else None
    return (
        code is not None
        and not any(mark in code for mark in _SHELL_MARKS)
        and _parsed_reads_only(code)
    )


def _program(args: tuple[str, ...], stdin_text: str) -> str | None:
    """The program text given with `-c` or on stdin, when no script or module comes first."""
    for position, arg in enumerate(args):
        match arg:
            case "-c":
                return args[position + 1] if position + 1 < len(args) else None
            case "-":
                return stdin_text or None
            case "-m":
                return None
            case _ if not arg.startswith("-"):
                return None
    return stdin_text or None


def _parsed_reads_only(code: str) -> bool:
    match attempt(
        lambda: ast.parse(code),
        "python_syntax",
        "inline Python",
        SyntaxError,
        ValueError,
    ):
        case Ok(tree):
            return not _may_write(tree)
        case _:
            return False


def _capable(name: str) -> bool:
    return name in CAPABLE or name.startswith(_CAPABLE_PREFIXES)


def _read_mode(call: ast.Call) -> bool:
    """`open(path)` and `open(path, "r…")`; any other mode, or one not spelled out, may write."""
    modes = [*call.args[1:2], *(k.value for k in call.keywords if k.arg == "mode")]
    return (
        not any(isinstance(arg, ast.Starred) for arg in call.args)
        and all(keyword.arg is not None for keyword in call.keywords)
        and all(
            isinstance(mode, ast.Constant)
            and isinstance(mode.value, str)
            and not set(mode.value) & _WRITING_MODE
            for mode in modes
        )
    )


def _may_write(node: ast.AST) -> bool:
    match node:
        case ast.Call(func=ast.Name(id="open"), args=args, keywords=keywords) if (
            _read_mode(node)
        ):
            return any(
                _may_write(child) for child in (*args, *(k.value for k in keywords))
            )
        case ast.Name(id=name) | ast.Attribute(attr=name) if _capable(name):
            return True
        case ast.Import(names=aliases):
            return any(alias.name.split(".")[0] not in READERS for alias in aliases)
        case ast.ImportFrom(module=module, names=aliases, level=0) if module:
            return module.split(".")[0] not in READERS or any(
                alias.name == "*" or _capable(alias.name) for alias in aliases
            )
        case ast.ImportFrom():
            return True
        case _:
            return any(_may_write(child) for child in ast.iter_child_nodes(node))
