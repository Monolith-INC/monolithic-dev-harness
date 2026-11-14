"""The discovery documents, defined once in `config/documents.toml`.

A document has a kind, a title, its sections in order, its interview areas and, when it is built
from another document, the upstream it maps from. `status` reads a document's content section by
section; `approved` reads its Status line. The loader refuses a catalog whose mappings do not line up.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from core.result import Ok, Result, attempt, bind, err, fmap, require, sequence

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PLUGIN_ROOT / "config" / "documents.toml"
HEADING = re.compile(r"^## (.+?)[ \t]*$", re.M)
State = Literal["complete", "placeholder", "missing"]


@dataclass(frozen=True)
class Upstream:
    kind: str
    gate: str
    map: dict[str, str]


@dataclass(frozen=True)
class Document:
    kind: str
    title: str
    sections: tuple[str, ...]
    interview: tuple[str, ...]
    upstream: Upstream | None


def load(path: Path = CONFIG) -> Result[dict[str, Document]]:
    return bind(
        _read(path),
        lambda data: bind(
            _documents(data),
            lambda docs: fmap(
                sequence(_linked(doc, docs) for doc in docs.values()),
                lambda _: docs,
            ),
        ),
    )


def status(doc: Document, content: str) -> dict[str, State]:
    """Each section of `doc` as complete, placeholder (empty or a bare TBD) or missing."""
    bodies = _bodies(content)
    return {
        section: _state(bodies[section]) if section in bodies else "missing"
        for section in doc.sections
    }


def approved(content: str) -> bool:
    """True when `Status: Approved` sits under the title, above the first level-2 heading."""
    first_section = HEADING.search(content)
    header = content[: first_section.start()] if first_section else content
    return any(line.strip() == "Status: Approved" for line in header.splitlines())


def substance(content: str) -> str:
    """What a reviewer approves in a document: all of it but the `Status` line under the title and
    the `Change history` section, the two parts that publishing it as approved changes."""
    kept: list[str] = []
    in_header = True
    in_history = False
    for line in content.splitlines():
        if heading := HEADING.match(line):
            in_header = False
            in_history = heading.group(1) == "Change history"
        if in_history or (in_header and line.strip().startswith("Status:")):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def _read(path: Path) -> Result[dict[str, Any]]:
    return bind(
        attempt(
            lambda: path.read_text(encoding="utf-8"),
            "invalid_documents",
            f"cannot read {path.name}",
            OSError,
        ),
        lambda text: attempt(
            lambda: tomllib.loads(text),
            "invalid_documents",
            f"{path.name} is not valid TOML",
            tomllib.TOMLDecodeError,
        ),
    )


def _documents(data: dict[str, Any]) -> Result[dict[str, Document]]:
    return fmap(
        sequence(_entry(kind, table) for kind, table in data.items()),
        lambda found: {doc.kind: doc for doc in found},
    )


def _entry(kind: str, table: Any) -> Result[Document]:
    return attempt(
        lambda: _document(kind, table),
        "invalid_documents",
        f"document {kind} is malformed",
        KeyError,
        TypeError,
        ValueError,
    )


def _document(kind: str, table: Any) -> Document:
    return Document(
        kind=kind,
        title=table["title"],
        sections=tuple(table["sections"]),
        interview=tuple(table["interview"]),
        upstream=_upstream(table["upstream"]) if "upstream" in table else None,
    )


def _upstream(table: Any) -> Upstream:
    return Upstream(table["kind"], table["gate"], dict(table["map"]))


def _linked(doc: Document, docs: dict[str, Document]) -> Result[None]:
    upstream = doc.upstream
    if upstream is None:
        return Ok(None)
    if upstream.kind not in docs:
        return err(
            "invalid_documents",
            f"{doc.kind} is built from {upstream.kind!r}, which is not in the catalog",
        )
    source = docs[upstream.kind]
    return fmap(
        sequence(
            _mapped(doc, source, from_section, to_section)
            for from_section, to_section in upstream.map.items()
        ),
        lambda _: None,
    )


def _mapped(
    doc: Document, source: Document, from_section: str, to_section: str
) -> Result[None]:
    return bind(
        require(
            from_section in source.sections,
            "invalid_documents",
            f"{source.kind} has no section {from_section!r} to map into {doc.kind}",
        ),
        lambda _: require(
            to_section in doc.sections,
            "invalid_documents",
            f"{doc.kind} has no section {to_section!r} for {source.kind} "
            f"section {from_section!r}",
        ),
    )


def _bodies(content: str) -> dict[str, str]:
    headings = list(HEADING.finditer(content))
    bodies: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        bodies.setdefault(heading.group(1), content[heading.end() : end].strip())
    return bodies


def _state(body: str) -> State:
    """A bare TBD is a placeholder. A TBD with its reason and owner is complete, as is any text."""
    return "placeholder" if body in ("", "TBD") else "complete"
