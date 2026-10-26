"""Pure transformation of project-local Git excludes owned by the installer."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from core.result import Ok, Result, bind, err

_PREFIX = "monolithic-dev-harness install excludes"
_BEGIN = re.compile(
    r"^# >>> " + re.escape(_PREFIX) + r" ([0-9a-f]{16}) >>>[ \t]*(?:\r?\n|$)"
)
_END = re.compile(
    r"^# <<< " + re.escape(_PREFIX) + r" ([0-9a-f]{16}) <<<[ \t]*(?:\r?\n|$)"
)
_BLOCK = re.compile(
    r"(?ms)(?:^|\r?\n)# >>> "
    + re.escape(_PREFIX)
    + r" ([0-9a-f]{16}) >>>[ \t]*(?:\r?\n|$)"
    r".*?^# <<< " + re.escape(_PREFIX) + r" \1 <<<[ \t]*(?:\r?\n|$)"
)
_MARKER = re.compile(r"^# (?:>>>|<<<) " + re.escape(_PREFIX) + r".*(?:\r?\n|$)")
_ESCAPE = frozenset("!#[ ]*?\\")
_OWNED = (Path(".harness/installation.json"),)


def _digest(project: Path) -> str:
    return hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:16]


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(str(path)))


def _pattern(path: Path, project: Path) -> str:
    relative = _absolute(path).relative_to(_absolute(project)).as_posix()
    escaped = "".join(
        "\\" + character if character in _ESCAPE else character
        for character in relative
    )
    return "/" + escaped


def _markers(text: str) -> Result[str]:
    lines = tuple(text.splitlines(keepends=True))
    malformed = tuple(
        line
        for line in lines
        if _PREFIX in line and _BEGIN.match(line) is None and _END.match(line) is None
    )
    begins = tuple(match.group(1) for line in lines if (match := _BEGIN.match(line)))
    ends = tuple(match.group(1) for line in lines if (match := _END.match(line)))
    blocks = tuple(_BLOCK.finditer(text))
    return (
        err(
            "installation_ignore_malformed",
            "managed Git exclude markers are malformed or unbalanced",
        )
        if malformed
        or sorted(begins) != sorted(ends)
        or len(set(begins)) != len(begins)
        or sum(
            match.group(0).count("# >>>") + match.group(0).count("# <<<")
            for match in blocks
        )
        != len(begins) + len(ends)
        else Ok(text)
    )


def _remove_block(text: str, digest: str) -> str:
    return _BLOCK.sub(
        lambda match: (
            ("" if match.group(1) == digest else match.group(0))
            if match.group(1) == digest
            else match.group(0)
        ),
        text,
    )


def _join(text: str, block: str) -> str:
    return text + ("\r\n" if text.endswith("\r\n") else "\n") + block


def _inside(project: Path, path: Path) -> bool:
    return (
        ".." not in path.parts
        and _absolute(path).is_relative_to(_absolute(project))
        and _absolute(path) != _absolute(project)
    )


def update(text: str, project: Path, paths: tuple[Path, ...]) -> Result[str]:
    digest = _digest(project)
    return bind(
        _markers(text),
        lambda _: (
            err(
                "installation_ignore_path",
                "managed Git exclude paths must be inside the project",
            )
            if not all(_inside(project, path) for path in paths)
            else Ok(
                _join(
                    _remove_block(text, digest),
                    "# >>> "
                    + _PREFIX
                    + f" {digest} >>>\n"
                    + "\n".join(
                        _pattern(
                            path if path.is_absolute() else project / path, project
                        )
                        for path in (*paths, *(project / owned for owned in _OWNED))
                    )
                    + f"\n# <<< {_PREFIX} {digest} <<<\n",
                )
            )
        ),
    )


def remove(text: str, project: Path) -> Result[str]:
    digest = _digest(project)
    return bind(_markers(text), lambda _: Ok(_remove_block(text, digest)))
