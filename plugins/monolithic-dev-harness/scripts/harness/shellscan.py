"""What a shell command runs, and what it could write.

One shared tokenization answers which commands run and which paths can be written.
Unlike regex-only scanning, this distinguishes `2>/dev/null` from writes and follows
`sudo git push` and `timeout 5 sh -c '…'`.

`invocations` follows lines, continuations, wrappers, subshells, control bodies, `sh -c`,
`eval`, `xargs` and `find -exec`, preserving each command's working directory.

`scan` classifies writes:
- `targets`: paths a command writes or removes.
- `trees`: directories whose whole contents a command may write or remove (`rm -r`, `git clean`,
  `find -delete`, extracting an archive).
- `unresolved`: words from commands whose writes cannot be followed (inline interpreter code, a
  script, `xargs` fed from a pipe, a path held in a variable). A caller treats a protected path
  among them as written: this fails closed, never open.

Unknown commands are writers of their named paths. Add verified readers to `NON_WRITERS`;
never exempt an unknown command merely because it names a protected file.
"""

from __future__ import annotations

import posixpath
import re
import shlex
import stat
import tarfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path

from harness.shell_literals import expansion_source
from harness.shell_parse_cache import parse

# Commands that never write a file's content. Anything else is a writer of what it names.
NON_WRITERS = frozenset(
    {
        *(
            "basename",
            "bat",
            "cat",
            "cmp",
            "column",
            "comm",
            "cut",
            "date",
            "diff",
            "dirname",
        ),
        *(
            "du",
            "echo",
            "false",
            "file",
            "fold",
            "grep",
            "head",
            "hexdump",
            "jq",
            "less",
        ),
        *(
            "ls",
            "mkdir",
            "more",
            "nl",
            "od",
            "paste",
            "printf",
            "pwd",
            "readlink",
            "realpath",
        ),
        *(
            "rg",
            "shellcheck",
            "stat",
            "strings",
            "tail",
            "test",
            "tr",
            "tree",
            "true",
        ),
        *("wc", "which", "[", "type"),
        *("b2sum", "cksum", "md5sum", "sha1sum", "sha224sum", "sha256sum", "sha384sum"),
        *("sha512sum", "shasum"),
    }
)
# Readers that write in place when given one of these flags.
IN_PLACE_FLAGS = {
    "sed": re.compile(r"^(-[a-zA-Z]*i|--in-place)"),
    "awk": re.compile(r"^(-i|--in-place|--inplace)$"),
    "gawk": re.compile(r"^(-i|--in-place|--inplace)$"),
    "yq": re.compile(r"^(-[a-zA-Z]*i|--inplace)"),
}
# Readers that write only the file named by one of these options.
OUTPUT_OPTIONS = {
    "sort": ("-o", "--output"),
    "tree": ("-o",),
    "less": ("-o", "-O", "--log-file", "--LOG-FILE"),
    "curl": ("-o", "--output"),
    "wget": ("-O", "--output-document"),
}
# Commands whose last operand is the destination; the rest are only read.
COPIERS = frozenset({"cp", "install", "rsync", "scp"})
# Commands known to write what they are given. Without the fail-closed default (see `scan`),
# only these, the tables above, and redirects count as writes.
KNOWN_WRITERS = frozenset(
    {"chgrp", "chmod", "chown", "ln", "mv", "tee", "touch", "truncate"}
)
# Commands that remove what they are given, recursively when asked to.
REMOVERS = frozenset({"rm", "rmdir", "shred", "unlink"})
SHELLS = frozenset({"sh", "bash", "dash", "zsh", "ksh", "fish"})
INTERPRETERS = re.compile(
    r"^(python[0-9.]*|node|nodejs|deno|bun|perl|ruby|php|osascript|lua)$"
)
# `<interpreter> -m <module>` invocations that only read.
READER_MODULES = frozenset({"json.tool"})
# Wrappers that run the command after them, and which of their options take a value.
WRAPPERS = {
    "command": frozenset(),
    "doas": frozenset({"-u", "-C"}),
    "env": frozenset({"-u", "--unset", "-C", "--chdir"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "nohup": frozenset(),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
    "sudo": frozenset({"-u", "-g", "-C", "-D", "-h", "-p", "-U", "-r", "-t", "-T"}),
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
    "time": frozenset({"-f", "--format", "-o", "--output"}),
    "exec": frozenset({"-a"}),
    "builtin": frozenset(),
}
# Nesting beyond this (eval inside eval inside `sh -c` …) is refused rather than followed.
MAX_DEPTH = 8
# Git subcommands that write working-tree paths they are given.
GIT_PATH_WRITERS = frozenset({"checkout", "restore", "rm", "mv"})
# Git subcommands that apply a patch file to the working tree.
GIT_PATCHERS = frozenset({"apply", "am"})
# A `find -name` pattern ending in a literal extension other than this one cannot select the
# harness's own records, which are all `.json` files.
_RECORD_EXTENSION = ".json"
_LITERAL_EXTENSION = re.compile(r"\.[A-Za-z0-9_]+$")

_REDIRECT_OUT = frozenset({">", ">>", ">|", "&>", "&>>", ">&", "<>"})
_CONTROL = frozenset({"&&", "||", ";", ";;", "&", "|", "|&", "(", ")"})
# Words that start or end a compound command; skipped where a command name would be.
_KEYWORDS = frozenset(
    {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "{", "}"}
)
# `2>/dev/null`, `1>&2`, `3<>file`: the number names a file descriptor, not an argument.
_FD_PREFIX = re.compile(r"(^|[\s;&|(])\d+(?=[<>])")
# A heredoc delimiter is a word; `$((1<<2))` is arithmetic, not a heredoc.
_DELIMITER = re.compile(r"-?[A-Za-z_][A-Za-z0-9_]*")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SUBSTITUTION = ("$", "`")
_WORD_SPLIT = re.compile(r"[\s'\"`;&|()<>,{}=\[\]]+")
_PATCH_PATH = re.compile(
    r"^(?:\+\+\+|---) \"?([^\t\"]+)|^diff --git (\S+) (\S+)|^(?:rename|copy) to (.+)$"
)
_PATCH_LIMIT = 2_000_000  # bytes; a larger patch is not read and counts as unreadable
_ARCHIVE_MEMBER_LIMIT = 50_000


@dataclass(frozen=True)
class Invocation:
    name: str
    args: tuple[str, ...]
    cwd: (
        str | None
    )  # relative to where the shell started; None when a `cd` cannot be followed
    redirects: tuple[tuple[str, str], ...] = ()
    stdin_text: str = ""  # a heredoc or here-string body
    piped_from: tuple[str, ...] = ()  # words of the commands piped into this one
    operands_from_pipe: bool = False  # run by xargs: its operands arrive on stdin
    parsed: bool = (
        True  # False when the line could not be tokenized and was split on whitespace
    )


@dataclass(frozen=True)
class ShellWrites:
    targets: tuple[str, ...]
    trees: tuple[str, ...]
    unresolved: tuple[str, ...]


@dataclass
class _Segment:
    words: list[str] = field(default_factory=list)
    redirects: list[tuple[str, str]] = field(default_factory=list)
    heredoc_delimiters: list[tuple[str, bool]] = field(default_factory=list)
    stdin_text: str = ""


def words_in(text: str) -> list[str]:
    """Path-like words inside arbitrary text: inline code, quoted strings, a heredoc body."""
    return [word for word in _WORD_SPLIT.split(text) if word]


_OPERATORS = sorted(
    (
        "&&",
        "||",
        ";;",
        "|&",
        "&>>",
        "&>",
        ">>",
        ">|",
        ">&",
        "<<<",
        "<<",
        "<&",
        "<>",
        "(",
        ")",
        ";",
        "|",
        "&",
        ">",
        "<",
    ),
    key=len,
    reverse=True,
)
_PUNCTUATION = set("();<>|&")


def _split_operators(token: str) -> list[str]:
    """shlex joins adjacent punctuation (`);`, `)|`); split it back into shell operators."""
    if not token or not set(token) <= _PUNCTUATION:
        return [token]
    parts = []
    while token:
        operator = next((op for op in _OPERATORS if token.startswith(op)), token[0])
        parts.append(operator)
        token = token[len(operator) :]
    return parts


def _tokens(line: str) -> tuple[list[str], bool]:
    line = _FD_PREFIX.sub(r"\1", line)
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        # shlex would end the line at any `#`, even inside a word (`a#b; git push`). Keeping
        # comments as words can only make a command look like it names more, never less.
        lexer.commenters = ""
        return [part for token in lexer for part in _split_operators(token)], True
    except ValueError:
        # An unbalanced quote. Keep going on whitespace so a `git push` or a redirect after it is
        # still seen; the caller treats the whole line as unresolved.
        spaced = re.sub(r"(&&|\|\||;|\||[()]|>>|>)", r" \1 ", line)
        return spaced.split(), False


def _parse_line(
    tokens: list[str],
) -> tuple[list[_Segment], list[tuple[str, _Segment | None]]]:
    """One line's simple commands, and the events between them."""
    segments: list[_Segment] = []
    events: list[tuple[str, _Segment | None]] = []
    current = _Segment()

    def flush(kind: str) -> _Segment:
        if current.words or current.redirects:
            segments.append(current)
            events.append(("run", current))
        events.append((kind, None))
        return _Segment()

    position = 0
    while position < len(tokens):
        token = tokens[position]
        following = tokens[position + 1] if position + 1 < len(tokens) else ""
        if token == "(":
            current = flush("open")
        elif token == ")":
            current = flush("close")
        elif token in {"|", "|&"}:
            current = flush("pipe")
        elif token in _CONTROL:
            current = flush("end")
        elif token in {"<", ">"} and following == "(":
            pass  # process substitution: the `(` that follows opens its own command
        elif token in _REDIRECT_OUT or token == "<":
            current.redirects.append((token, following))
            position += 1
        elif token == "<<" and _DELIMITER.fullmatch(following):
            # `<<-EOF` tokenizes as `<<` then `-EOF`; quotes around the delimiter are already gone.
            current.heredoc_delimiters.append(
                (following.lstrip("-"), following.startswith("-"))
            )
            position += 1
        elif token == "<<<":
            current.stdin_text += following + "\n"
            position += 1
        elif token in _KEYWORDS and not current.words:
            pass
        else:
            current.words.append(token)
        position += 1
    flush("end")
    return segments, events


def _segments(command: str) -> Iterator[tuple[str, _Segment | None, bool]]:
    """Yield ("run", segment, parsed), or ("pipe" | "end" | "open" | "close", None, parsed)."""
    lines = command.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        # A trailing backslash continues the command; inside a heredoc body it is just text,
        # so continuations are joined here and not before the body is read.
        while line.endswith("\\") and index < len(lines):
            line = line[:-1] + " " + lines[index]
            index += 1
        tokens, parsed = _tokens(line)
        segments, events = _parse_line(tokens)
        # A heredoc's body is the lines that follow, up to its delimiter.
        for segment in segments:
            for delimiter, dash in segment.heredoc_delimiters:
                body: list[str] = []
                while index < len(lines):
                    line = lines[index]
                    index += 1
                    if (line.strip() if dash else line) == delimiter:
                        break
                    body.append(line)
                segment.stdin_text += "\n".join(body) + "\n"
        for kind, segment in events:
            yield kind, segment, parsed


def _unwrap(words: list[str]) -> list[str]:
    words = list(words)
    while words and _ASSIGNMENT.match(words[0]):
        words.pop(0)
    while words:
        wrapper = posixpath.basename(words[0])
        if wrapper not in WRAPPERS:
            break
        words.pop(0)
        takes_value = WRAPPERS[wrapper]
        while words and words[0].startswith("-") and words[0] != "--":
            flag = words.pop(0)
            if wrapper == "env" and flag in {"-S", "--split-string"} and words:
                words = shlex.split(words[0]) + words[1:]
                continue
            if flag in takes_value and words:
                words.pop(0)
        if words and words[0] == "--":
            words.pop(0)
        while wrapper == "env" and words and _ASSIGNMENT.match(words[0]):
            words.pop(0)
        if wrapper == "timeout" and words:
            words.pop(0)  # the duration
    return words


def _resolve(path: str, cwd: str | None) -> str:
    if path.startswith(("/", "~")) or cwd is None:
        return posixpath.normpath(path) if path.startswith("/") else path
    return posixpath.normpath(posixpath.join(cwd or ".", path))


resolve = _resolve  # noqa: E305 - public alias for the rules


def _substitutions(command: str) -> list[str]:
    """The commands inside `$(…)` and backticks, which run before the command that holds them."""
    found = []
    for match in re.finditer(r"`([^`]*)`", command):
        found.append(match.group(1))
    position = 0
    while (start := command.find("$(", position)) != -1:
        if command.startswith("$((", start):
            position = start + 3  # arithmetic, not a command
            continue
        depth, index = 1, start + 2
        while index < len(command) and depth:
            depth += {"(": 1, ")": -1}.get(command[index], 0)
            index += 1
        found.append(command[start + 2 : index - 1])
        position = index
    return found


def invocations(command: str, cwd: str | None = "", depth: int = 0) -> list[Invocation]:
    return parse(_invocations, command, cwd, depth)


def _invocations(
    command: str, cwd: str | None = "", depth: int = 0
) -> list[Invocation]:
    """Every simple command `command` runs, in order, including nested and dispatched ones."""
    if depth > MAX_DEPTH:
        # Raising makes the hook refuse the call, as it does for any command it cannot read.
        raise ValueError(f"the command nests more than {MAX_DEPTH} levels deep")
    found: list[Invocation] = []
    for inner in _substitutions(expansion_source(command)):
        found.extend(invocations(inner, cwd, depth + 1))
    stack: list[str | None] = []
    pipeline: list[str] = []
    for kind, segment, parsed in _segments(command):
        if kind == "open":
            stack.append(cwd)
            continue
        if kind == "close":
            cwd = stack.pop() if stack else cwd
            pipeline = []
            continue
        if kind == "end":
            pipeline = []
            continue
        if kind == "pipe" or segment is None:
            continue
        words = _unwrap(segment.words)
        name = posixpath.basename(words[0]) if words else ""
        args = tuple(words[1:])
        if name in {"cd", "pushd"}:
            destination = next((a for a in args if not a.startswith("-")), "")
            if not destination or destination == "-":
                cwd = "~"
            elif destination.startswith(_SUBSTITUTION):
                cwd = None
            else:
                cwd = _resolve(destination, cwd)
        invocation = Invocation(
            name=name,
            args=args,
            cwd=cwd,
            redirects=tuple(segment.redirects),
            stdin_text=segment.stdin_text,
            piped_from=tuple(pipeline),
            parsed=parsed,
        )
        found.append(invocation)
        found.extend(_dispatched(invocation, depth))
        pipeline.extend(segment.words)
    return found


def plain_git_context(command: str) -> bool:
    """Staging exemptions require Git-only calls with no environment-changing wrappers."""
    return all(
        invocation.name == "git" for invocation in invocations(command)
    ) and not any(
        _ASSIGNMENT.match(word)
        or posixpath.basename(word)
        in {"env", "export", "declare", "typeset", "local", "setenv"}
        for _, segment, _ in _segments(command)
        if segment is not None
        for word in segment.words
    )


def _dispatched(invocation: Invocation, depth: int = 0) -> list[Invocation]:
    """Commands another command runs for it: `sh -c`, `eval`, `xargs`, `find -exec`."""
    name, args = invocation.name, list(invocation.args)
    if name in SHELLS:
        if "-c" in args[:-1]:
            script = next((a for a in args[args.index("-c") + 1 :] if a != "--"), "")
            return invocations(script, invocation.cwd, depth + 1)
        if invocation.stdin_text and not any(not a.startswith("-") for a in args):
            return invocations(invocation.stdin_text, invocation.cwd, depth + 1)
        return []
    if name == "eval":
        return invocations(" ".join(args), invocation.cwd, depth + 1)
    if name == "xargs":
        words = list(args)
        while words and words[0].startswith("-"):
            flag = words.pop(0)
            if flag in {"-I", "-L", "-n", "-P", "-d", "-E", "-s", "-a"} and words:
                words.pop(0)
        inner = _unwrap(words)
        if not inner:
            return []
        return [
            Invocation(
                name=posixpath.basename(inner[0]),
                args=tuple(inner[1:]),
                cwd=invocation.cwd,
                piped_from=invocation.piped_from,
                operands_from_pipe=True,
                parsed=invocation.parsed,
            )
        ]
    if name == "find":
        found: list[Invocation] = []
        for position, arg in enumerate(args):
            if arg in {"-exec", "-execdir", "-ok", "-okdir"}:
                end = next(
                    (
                        i
                        for i in range(position + 1, len(args))
                        if args[i] in {";", "+"}
                    ),
                    len(args),
                )
                inner = _unwrap(args[position + 1 : end])
                if inner:
                    found.append(
                        Invocation(
                            name=posixpath.basename(inner[0]),
                            args=tuple(a for a in inner[1:] if a != "{}"),
                            cwd=invocation.cwd,
                            parsed=invocation.parsed,
                        )
                    )
        return found
    return []


# --- what an invocation writes ------------------------------------------------------------------


@dataclass
class _Writes:
    targets: list[str] = field(default_factory=list)
    trees: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


def _operands(args: tuple[str, ...]) -> list[str]:
    return [a for a in args if a and not a.startswith("-") and a != "{}"]


def _option_values(args: tuple[str, ...], options: tuple[str, ...]) -> list[str]:
    values = []
    for position, arg in enumerate(args):
        for option in options:
            if arg == option and position + 1 < len(args):
                values.append(args[position + 1])
            elif option.startswith("--") and arg.startswith(option + "="):
                values.append(arg.split("=", 1)[1])
            elif (
                not option.startswith("--")
                and arg.startswith(option)
                and len(arg) > len(option)
            ):
                values.append(arg[len(option) :])
    return values


def _regular_file(
    path: str, cwd: str | None, base: Path | None, limit: int
) -> Path | None:
    """The file behind `path` if it is a regular file no larger than `limit` bytes."""
    resolved = _resolve(path, cwd)
    candidate = (
        base / resolved if base and not resolved.startswith("/") else Path(resolved)
    )
    try:
        info = candidate.stat()
    except OSError:
        return None
    return candidate if stat.S_ISREG(info.st_mode) and info.st_size <= limit else None


def _patch_paths(path: str, cwd: str | None, base: Path | None) -> list[str] | None:
    """Every path a patch file could write, or None if it cannot be read.

    Prefixes are stripped by `-p`, which the reader does not track, so each path is reported with
    every leading component removed in turn.
    """
    file = _regular_file(path, cwd, base, _PATCH_LIMIT)
    if file is None:
        return None
    try:
        text = file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found = []
    for line in text.splitlines():
        match = _PATCH_PATH.match(line)
        if not match:
            continue
        for candidate in (group for group in match.groups() if group):
            candidate = candidate.strip().strip('"')
            if candidate == "/dev/null":
                continue
            parts = candidate.split("/")
            found.extend(_resolve("/".join(parts[i:]), cwd) for i in range(len(parts)))
    return found


def _archive_members(path: str, cwd: str | None, base: Path | None) -> list[str] | None:
    """Member names of an archive, or None if it cannot be listed completely and safely."""
    archive = _regular_file(path, cwd, base, 1 << 34)
    if archive is None:
        return None
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as handle:
                names = handle.namelist()
        else:
            with tarfile.open(archive) as handle:
                members = list(islice(handle, _ARCHIVE_MEMBER_LIMIT + 1))
                if any(m.issym() or m.islnk() for m in members):
                    return None  # a link member can point a later write anywhere
                names = [m.name for m in members]
    except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError):
        return None
    return None if len(names) > _ARCHIVE_MEMBER_LIMIT else names


def _classify(
    invocation: Invocation,
    writes: _Writes,
    base: Path | None,
    whole: str,
    probing: bool = False,
    unknown_writes: bool = True,
) -> None:
    name, args, cwd = invocation.name, invocation.args, invocation.cwd

    def places(path: str) -> list[str]:
        # A `cd` that fails leaves the shell where it was, so a relative path is checked both
        # from the tracked directory and from where the command started.
        resolved = [_resolve(path, cwd)]
        if cwd and not path.startswith(("/", "~")):
            resolved.append(_resolve(path, ""))
        return resolved

    def target(path: str) -> None:
        if cwd is None or any(mark in path for mark in _SUBSTITUTION):
            unresolved(whole)
        writes.targets.extend(places(path))

    def tree(path: str) -> None:
        if cwd is None or any(mark in path for mark in _SUBSTITUTION):
            unresolved(whole)
        writes.trees.extend(places(path))

    def unresolved(*texts: str) -> None:
        # A name inside inline code or a script's arguments is relative to where it runs.
        for text in texts:
            for word in words_in(text):
                writes.unresolved.append(word)
                if cwd:
                    writes.unresolved.append(_resolve(word, cwd))

    for operator, path in invocation.redirects:
        if operator == "<" or not path:
            continue
        if operator == ">&" and path.isdigit():
            continue
        if path != "/dev/null":
            # `target` treats a `$VAR` or backtick in the path as naming anything on the line.
            target(path)
    if not invocation.parsed:
        unresolved(" ".join((name, *args)))
    if (
        not probing
        and any(mark in arg for arg in args for mark in _SUBSTITUTION)
        and _writes_operands(invocation)
    ):
        unresolved(whole)
    if not name or name in {"cd", "pushd", "eval"}:
        return

    if name in SHELLS:
        # `sh -c` and a heredoc were walked as their own invocations; a script or a pipe was not.
        if "-c" not in args[:-1] and not invocation.stdin_text:
            unresolved(" ".join(args), " ".join(invocation.piped_from))
        return
    if INTERPRETERS.match(name):
        if args[:1] == ("-m",) and len(args) > 1 and args[1] in READER_MODULES:
            return
        unresolved(" ".join(args), invocation.stdin_text)
        return
    if name == "xargs":
        return  # its command was walked on its own
    if name == "find":
        _classify_find(args, tree, target)
        return
    if name == "git":
        _classify_git(invocation, base, writes, whole)
        return
    if name in {"tar", "bsdtar"}:
        mode, archive, destinations = _tar_options(args)
        if "x" in mode:
            _extract(archive, destinations or ["."], cwd, base, writes)
        elif set(mode) & {"c", "r", "u", "A"} and archive:
            target(archive)
        return
    if name == "unzip":
        if "-l" in args or "-t" in args or "-v" in args:
            return
        operands = _operands(
            tuple(a for a in args if a not in _option_values(args, ("-d",)))
        )
        _extract(
            operands[0] if operands else None,
            _option_values(args, ("-d",)) or ["."],
            cwd,
            base,
            writes,
        )
        return
    if name == "patch":
        sources = _option_values(args, ("-i", "--input"))
        sources += [path for op, path in invocation.redirects if op == "<"]
        directory = _option_values(args, ("-d", "--directory"))
        into = _resolve(directory[-1], cwd) if directory and cwd is not None else cwd
        _apply_patches(sources, into, base, writes, whole, invocation)
        return
    if name == "dd":
        for arg in args:
            if arg.startswith("of="):
                target(arg[3:])
        return
    if name in OUTPUT_OPTIONS:
        for value in _option_values(args, OUTPUT_OPTIONS[name]):
            target(value)
        if name == "wget" and not _option_values(args, OUTPUT_OPTIONS[name]):
            target(".")
        if name == "curl" and ("-O" in args or "--remote-name" in args):
            target(".")
        return
    if name in IN_PLACE_FLAGS:
        if any(IN_PLACE_FLAGS[name].match(arg) for arg in args):
            for operand in _operands(args):
                target(operand)
        return
    if name in NON_WRITERS:
        return
    if name in REMOVERS:
        recursive = any(
            re.match(r"^-[a-zA-Z]*[rR]", arg) or arg == "--recursive" for arg in args
        )
        for operand in _operands(args):
            (tree if recursive else target)(operand)
        return
    if name in COPIERS:
        destination = _option_values(args, ("-t", "--target-directory"))
        operands = _operands(args)
        for path in destination or operands[-1:]:
            (tree if name == "rsync" else target)(path)
        if name == "rsync" and any(a.startswith("--remove-source") for a in args):
            for path in operands[:-1]:
                target(path)
        return
    # Any other command: assume it writes every path it names, including `--opt=path` values,
    # unless the caller asked for positive evidence only.
    if not unknown_writes and name not in KNOWN_WRITERS:
        return
    for arg in args:
        if arg.startswith("-") and "=" in arg:
            target(arg.split("=", 1)[1])
        elif arg and not arg.startswith("-"):
            target(arg)


def _classify_find(args, tree, target) -> None:
    starts = []
    for arg in args:
        if arg.startswith("-") or arg in {"(", "!", ")"}:
            break
        starts.append(arg)
    starts = starts or ["."]
    patterns = [
        args[i + 1] for i, a in enumerate(args[:-1]) if a in {"-name", "-iname"}
    ]
    # `-name '*.tmp'` cannot select a `.json` record; `-name 'HB-*'` or `-iname '*.JSON'` can.
    narrowed = (
        bool(patterns)
        and all(
            (match := _LITERAL_EXTENSION.search(pattern)) is not None
            and match.group().lower() != _RECORD_EXTENSION
            for pattern in patterns
        )
        and not any(
            a in {"-path", "-ipath", "-regex", "-iregex", "-wholename"} for a in args
        )
    )
    for position, arg in enumerate(args):
        if arg in {"-fprint", "-fprint0", "-fprintf", "-fls"} and position + 1 < len(
            args
        ):
            target(args[position + 1])
    writes = "-delete" in args or any(
        a in {"-exec", "-execdir", "-ok", "-okdir"} and _exec_writes(args[i + 1 :])
        for i, a in enumerate(args)
    )
    if writes and not narrowed:
        for start in starts:
            tree(start)


def _exec_writes(rest: tuple[str, ...]) -> bool:
    inner = _unwrap(list(rest))
    if not inner:
        return False
    name = posixpath.basename(inner[0])
    if name in IN_PLACE_FLAGS:
        return any(IN_PLACE_FLAGS[name].match(a) for a in inner[1:])
    return name not in NON_WRITERS


def _apply_patches(
    sources: list[str],
    cwd: str | None,
    base: Path | None,
    writes: _Writes,
    whole: str,
    invocation: Invocation,
) -> None:
    """A patch writes the paths it names.

    One that cannot be read now — piped in, missing, too large, or written earlier in the same
    command (so what is read here is not what gets applied) — could write anything under the
    directory it is applied in. Writing the patch and applying it in two steps avoids that.
    """
    written_here = set(writes.targets)
    readable = [
        _patch_paths(source, cwd, base)
        if _resolve(source, cwd) not in written_here
        else None
        for source in sources
    ]
    if not sources or any(paths is None for paths in readable):
        writes.trees.append(_resolve(".", cwd) if cwd is not None else ".")
        writes.unresolved.extend(words_in(whole))
    for paths in readable:
        writes.targets.extend(paths or [])


def _classify_git(invocation: Invocation, base, writes: _Writes, whole: str) -> None:
    cwd, rest = invocation.cwd, list(invocation.args)
    while rest and rest[0].startswith("-"):
        flag = rest.pop(0)
        if flag in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"} and rest:
            value = rest.pop(0)
            if flag == "-C":
                cwd = _resolve(value, cwd)
    if not rest:
        return
    subcommand, options = rest[0], tuple(rest[1:])
    if subcommand in GIT_PATH_WRITERS:
        # A pathspec can be a directory (`git checkout -- .`), so each one is a whole tree.
        paths = (
            list(options[options.index("--") + 1 :])
            if "--" in options
            else _operands(options)
        )
        writes.trees.extend(_resolve(path, cwd) for path in paths)
    elif subcommand == "clean":
        writes.trees.extend(_resolve(path, cwd) for path in _operands(options) or ["."])
    elif subcommand == "stash" and any(
        a in {"-u", "--include-untracked", "-a", "--all"} for a in options
    ):
        writes.trees.append(_resolve(".", cwd))
    elif subcommand in GIT_PATCHERS:
        directory = _option_values(options, ("--directory",))
        into = _resolve(directory[-1], cwd) if directory and cwd is not None else cwd
        sources = [a for a in _operands(options) if not a.startswith("--")]
        sources += [path for op, path in invocation.redirects if op == "<"]
        _apply_patches(sources, into, base, writes, whole, invocation)


def _tar_options(args) -> tuple[str, str | None, list[str]]:
    """(mode letters, archive, extraction directories) from GNU/BSD tar arguments."""
    tokens = list(args)
    if tokens and not tokens[0].startswith("-"):
        tokens[0] = "-" + tokens[0]  # the old bundled form: `tar xf archive`
    mode, archive, destinations = "", None, []
    position = 0
    while position < len(tokens):
        token = tokens[position]
        following = tokens[position + 1] if position + 1 < len(tokens) else ""
        if token.startswith("--"):
            key, has_value, value = token.partition("=")
            if key in {"--file", "--directory"}:
                if not has_value:
                    value, position = following, position + 1
                if key == "--file":
                    archive = value
                else:
                    destinations.append(value)
            elif key in {"--extract", "--get"}:
                mode += "x"
            elif key in {
                "--create",
                "--append",
                "--update",
                "--delete",
                "--concatenate",
            }:
                mode += "c"
        elif token.startswith("-") and len(token) > 1:
            letters = token[1:]
            for index, letter in enumerate(letters):
                if letter in "xtcruA":
                    mode += letter
                if letter in "fC":
                    value = letters[index + 1 :]
                    if not value:
                        value, position = following, position + 1
                    if letter == "f":
                        archive = value
                    else:
                        destinations.append(value)
                    break
        position += 1
    return mode, archive, destinations


def _extract(archive, destinations, cwd, base, writes: _Writes) -> None:
    """An extraction writes its members; if they cannot be listed, anything under the directory."""
    members = _archive_members(archive, cwd, base) if archive else None
    for destination in destinations:
        if members is None:
            writes.trees.append(_resolve(destination, cwd))
        else:
            writes.targets.extend(
                _resolve(posixpath.join(destination, member), cwd) for member in members
            )


def _writes_operands(invocation: Invocation) -> bool:
    """Whether this command would write a path given as an operand."""
    probe = _Writes()
    _classify(
        Invocation(invocation.name, (*invocation.args, "\x00"), invocation.cwd),
        probe,
        None,
        "",
        probing=True,
    )
    return any("\x00" in path for path in probe.targets + probe.trees)


def scan(
    command: str,
    cwd: str | None = "",
    base: Path | None = None,
    unknown_writes: bool = True,
) -> ShellWrites:
    """What `command`, started in `cwd` (relative to `base`), could write.

    `unknown_writes=False` drops the fail-closed default for commands this module does not know
    (`flutter test`, `harness doctor`): they count as writing nothing. The protection rules keep the
    default; a check that only asks "is this plainly a write?" turns it off.
    """
    writes = _Writes()
    for invocation in invocations(command, cwd):
        _classify(invocation, writes, base, command, unknown_writes=unknown_writes)
        if invocation.operands_from_pipe and _writes_operands(invocation):
            writes.unresolved.extend(words_in(" ".join(invocation.piped_from)))
    return ShellWrites(
        tuple(dict.fromkeys(writes.targets)),
        tuple(dict.fromkeys(writes.trees)),
        tuple(dict.fromkeys(writes.unresolved)),
    )


def git_commands(
    command: str, cwd: str | None = ""
) -> list[tuple[str | None, list[str]]]:
    """Every `git` the command runs: (its directory, argv after git's own options).

    Walks the same invocations as `scan`, so `sudo git push`, `(git push)`, `git status && git
    commit`, and `if …; then git push; fi` are all seen.
    """
    found: list[tuple[str | None, list[str]]] = []
    for invocation in invocations(command, cwd):
        if invocation.name != "git":
            continue
        directory = invocation.cwd or None
        rest = list(invocation.args)
        while rest and rest[0].startswith("-"):
            flag = rest.pop(0)
            if flag in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"} and rest:
                value = rest.pop(0)
                if flag == "-C":
                    directory = _resolve(value, directory or "")
        found.append((directory, rest))
    return found


def writes_inside(command: str, root: Path | None = None) -> bool:
    """Whether the command plainly writes a file inside `root` (the repository).

    Positive evidence only: a redirect, or a command known to write. Redirects to `/dev/null`,
    file-descriptor redirects such as `2>&1`, writes outside the repository (`/tmp`), and commands
    this module does not know (`flutter test`) do not count.
    """
    writes = scan(command, "", root, unknown_writes=False)
    for path in (*writes.targets, *writes.trees):
        if not path.startswith(("/", "~")):
            return True
        if root is not None:
            try:
                Path(path).resolve().relative_to(Path(root).resolve())
                return True
            except ValueError:
                continue
    return False
