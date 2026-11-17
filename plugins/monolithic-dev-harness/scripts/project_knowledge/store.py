"""Read-only project knowledge, adapted from monolithic-code-review-toolkit.

Retrieval contract inspired by MIT-licensed adapter at commit
3af148b44421521bb453be0abea05750e45f6f8a. This implementation is independent.
"""

from __future__ import annotations

import difflib
import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import reduce
from pathlib import Path
from typing import Any

from project_knowledge.stem import normalize_token


class StoreError(Exception):
    """A store cannot be read safely."""


class UnknownUnit(StoreError):
    def __init__(self, unit_id: str, nearest: tuple[str, ...]) -> None:
        self.unit_id = unit_id
        self.nearest = nearest
        super().__init__(
            f"unknown knowledge unit: {unit_id}; closest: {', '.join(nearest)}"
        )


MANIFEST_NAME = "manifest.md"


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


_TOKEN = re.compile(r"[a-z0-9]+")
_HEADING = re.compile(r"^(#{2,3})\s+(.*?)\s*$")
_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_LIST_FIELDS = frozenset({"sources", "links", "supersedes"})


def normalize(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(
        normalize_token(item)
        for item in _TOKEN.findall(normalize(text))
        if len(item) > 1
    )


def _scalar(text: str) -> str:
    value = text.strip()
    return (
        value[1:-1]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'"
        else value
    )


def _field(state: tuple[dict[str, Any], str], line: str) -> tuple[dict[str, Any], str]:
    fields, key = state
    match line.strip():
        case text if text.startswith("- ") and key:
            return ({**fields, key: (*fields.get(key, ()), _scalar(text[2:]))}, key)
        case text if ":" in text:
            name, _, raw = text.partition(":")
            value = raw.strip()
            result = (
                tuple(_scalar(x) for x in value[1:-1].split(",") if x.strip())
                if value.startswith("[") and value.endswith("]")
                else ()
                if not value
                else _scalar(value)
            )
            return ({**fields, name.strip(): result}, name.strip())
        case _:
            return state


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match text.startswith("---\n"), text.find("\n---\n", 3):
        case True, int() as end if end >= 0:
            fields, _ = reduce(_field, text[4:end].splitlines(), ({}, ""))
            return fields, text[end + 5 :]
        case _:
            return {}, text


def dump_frontmatter(fields: dict[str, Any]) -> str:
    def render(item: tuple[str, Any]) -> tuple[str, ...]:
        key, value = item
        match value:
            case list() | tuple():
                return (
                    (f"{key}: []",)
                    if not value
                    else (f"{key}:", *(f"  - {v}" for v in value))
                )
            case _:
                return (
                    f'{key}: "{value}"' if ":" in str(value) else f"{key}: {value}",
                )

    return "\n".join(
        (
            "---",
            *(line for item in sorted(fields.items()) for line in render(item)),
            "---",
            "",
        )
    )


def _tsv(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    size = next(
        (i for i, line in enumerate(lines) if not line.startswith("#")), len(lines)
    )
    fields = dict(
        (
            key.strip(),
            tuple(x.strip() for x in value.split(",") if x.strip())
            if key.strip() in _LIST_FIELDS
            else _scalar(value),
        )
        for line in lines[:size]
        for key, sep, value in (line[1:].strip().partition(":"),)
        if sep
    )
    return fields, "".join(lines[size:])


@dataclass(frozen=True)
class Section:
    unit_id: str
    anchor: str
    title: str
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True)
class Unit:
    id: str
    path: Path
    fields: dict[str, Any]
    body: str
    raw: str
    version: str

    def sections(self) -> tuple[Section, ...]:
        lines = self.body.splitlines()

        def visit(
            state: tuple[bool, tuple[tuple[int, str], ...]], item: tuple[int, str]
        ) -> tuple[bool, tuple[tuple[int, str], ...]]:
            fenced, marks = state
            number, line = item
            match line.lstrip().startswith("```"), fenced, _HEADING.match(line):
                case True, _, _:
                    return not fenced, marks
                case False, False, re.Match() as found:
                    return fenced, (*marks, (number, found.group(2)))
                case _:
                    return state

        _, marks = reduce(visit, enumerate(lines), (False, ()))
        match marks:
            case ():
                return (
                    Section(
                        self.id,
                        "",
                        str(self.fields.get("title", self.id)),
                        1,
                        max(len(lines), 1),
                        self.body,
                    ),
                )
            case _:
                preamble = (
                    (
                        Section(
                            self.id,
                            "",
                            str(self.fields.get("title", self.id)),
                            1,
                            marks[0][0],
                            "\n".join(lines[: marks[0][0]]).strip(),
                        ),
                    )
                    if marks[0][0] and "\n".join(lines[: marks[0][0]]).strip()
                    else ()
                )
                return (
                    *preamble,
                    *(
                        Section(
                            self.id,
                            re.sub(
                                r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalize(title))
                            ).strip("-"),
                            title,
                            start + 1,
                            end,
                            "\n".join(lines[start:end]).strip(),
                        )
                        for (start, title), end in zip(
                            marks, (*(n for n, _ in marks[1:]), len(lines)), strict=True
                        )
                    ),
                )

    def outbound_links(self) -> tuple[str, ...]:
        values = self.fields.get("links", ())
        values = (values,) if isinstance(values, str) else values
        return tuple(
            dict.fromkeys(
                x.strip()
                for item in (*values, self.body)
                for x in (_LINK.findall(item) or ([item] if item != self.body else []))
                if x.strip()
            )
        )


@dataclass(frozen=True)
class Hit:
    unit_id: str
    anchor: str
    title: str
    start_line: int
    end_line: int
    score: float
    matched_terms: tuple[str, ...]
    snippet: str


@dataclass(frozen=True)
class KnowledgeStore:
    root: Path

    @property
    def units(self) -> dict[str, Unit]:
        root = self.root.resolve()
        paths = tuple(
            path
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root)
            and ".legacy" not in path.relative_to(root).parts
            and path.suffix in {".md", ".tsv"}
            and path.name not in {"catalog.tsv", "manifest.md"}
        )
        units = tuple(_read_unit(path, root) for path in paths)
        match len({unit.id for unit in units}) == len(units):
            case False:
                raise StoreError("duplicate knowledge unit id")
            case True:
                return {unit.id: unit for unit in units}

    def unit(self, identifier: str) -> Unit:
        units = self.units
        match units.get(identifier):
            case None:
                raise UnknownUnit(
                    identifier,
                    tuple(
                        difflib.get_close_matches(
                            identifier, sorted(units), n=5, cutoff=0.4
                        )
                    ),
                )
            case unit:
                return unit

    def catalog(
        self,
        path_prefix: str | None = None,
        type: str | None = None,
        updated_after: str | None = None,
    ) -> list[dict[str, str]]:
        return [
            {
                "id": u.id,
                "type": str(u.fields.get("type", "")),
                "area": str(u.fields.get("area", "")),
                "title": str(u.fields.get("title", u.id)),
                "path": str(u.path.relative_to(self.root.resolve())),
                "provenance": str(u.fields.get("provenance", "assumed")),
                "updated": str(u.fields.get("updated", "")),
                "read_when": str(u.fields.get("read_when", "")),
            }
            for u in sorted(self.units.values(), key=lambda u: u.id)
            if u.fields.get("status", "current") == "current"
            and (not path_prefix or u.id.startswith(path_prefix.strip("/")))
            and (not type or u.fields.get("type") == type)
            and (not updated_after or str(u.fields.get("updated", "")) > updated_after)
        ]

    def find(
        self,
        terms: str,
        path_prefix: str | None = None,
        type: str | None = None,
        area: str | None = None,
        status: str | None = "current",
        limit: int = 8,
    ) -> tuple[list[Hit], dict[str, Any]]:
        units = tuple(
            u
            for u in self.units.values()
            if (not path_prefix or u.id.startswith(path_prefix.strip("/")))
            and (not type or u.fields.get("type") == type)
            and (not area or u.fields.get("area") == area)
            and (not status or u.fields.get("status", "current") == status)
        )
        documents = tuple(
            (
                u,
                section,
                tokenize(
                    section.text
                    + " "
                    + u.id.replace("/", " ")
                    + " "
                    + str(u.fields.get("title", ""))
                    + " "
                    + str(u.fields.get("read_when", ""))
                ),
            )
            for u in units
            for section in u.sections()
        )
        query = tuple(dict.fromkeys(tokenize(terms)))
        original_terms = tuple(dict.fromkeys(_TOKEN.findall(normalize(terms))))
        total = len(documents)
        average = sum(len(tokens) for _, _, tokens in documents) / total if total else 0

        def score(tokens: tuple[str, ...], term: str) -> float:
            frequency = tokens.count(term)
            docs = sum(term in item for _, _, item in documents)
            return (
                math.log(1 + (total - docs + 0.5) / (docs + 0.5))
                * (frequency * 2.5)
                / (frequency + 1.5 * (1 - 0.75 + 0.75 * len(tokens) / (average or 1)))
                if frequency
                else 0
            )

        hits = sorted(
            (
                Hit(
                    u.id,
                    section.anchor,
                    section.title,
                    section.start_line,
                    section.end_line,
                    round(sum(score(tokens, q) for q in query), 4),
                    tuple(q for q in original_terms if normalize_token(q) in tokens),
                    section.text[:240],
                )
                for u, section, tokens in documents
                if any(q in tokens for q in query)
            ),
            key=lambda hit: (-hit.score, hit.unit_id, hit.anchor),
        )[: max(1, min(limit, 50))]
        vocabulary = sorted({item for _, _, tokens in documents for item in tokens})
        guidance = (
            {}
            if hits
            else {
                "reason": "no section matched every filter and at least one term",
                "unit_count": len(self.units),
                "candidates_after_filters": len(units),
                "facets": {
                    field: sorted(
                        {str(u.fields.get(field)) for u in units if u.fields.get(field)}
                    )
                    for field in ("type", "area", "status")
                },
                "near_miss_terms": sorted(
                    {
                        word
                        for term in query
                        for word in difflib.get_close_matches(
                            term, vocabulary, n=3, cutoff=0.7
                        )
                    }
                    - set(query)
                ),
                "nearest_units": sorted(u.id for u in units)[:5],
            }
        )
        return hits, guidance

    def fetch(
        self,
        unit_id: str,
        anchor: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        start_column: int = 0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        unit = self.unit(unit_id)
        sections = (
            tuple(s for s in unit.sections() if s.anchor == anchor) if anchor else ()
        )
        match anchor, sections:
            case str(), ():
                raise StoreError(
                    f"unknown section: {anchor}; available: {', '.join(section.anchor for section in unit.sections() if section.anchor)}"
                )
            case _:
                pass
        offset = len(unit.raw.splitlines()) - len(unit.body.splitlines())
        first = offset + sections[0].start_line if sections else start_line or 1
        selected = (
            sections[0].text
            if sections
            else "\n".join(unit.raw.splitlines()[first - 1 : end_line])
        )
        selected = selected[start_column:]
        budget = max_tokens * 4 if max_tokens is not None else len(selected)
        text = selected[:budget]
        truncated = len(selected) > budget
        prefix = selected[:budget]
        continuation = (
            {
                "id": unit.id,
                "anchor": None,
                "start_line": first + prefix.count("\n"),
                "start_column": len(prefix.rsplit("\n", 1)[-1])
                + (start_column if "\n" not in prefix else 0),
                "remaining_lines": selected[budget:].count("\n") + 1,
            }
            if truncated
            else None
        )
        return {
            "id": unit.id,
            "version": unit.version,
            "provenance": str(unit.fields.get("provenance", "assumed")),
            "status": str(unit.fields.get("status", "current")),
            "updated": str(unit.fields.get("updated", "")),
            "anchor": anchor,
            "content": text,
            "truncated": truncated,
            "continuation": continuation,
        }

    def links(self, unit_id: str, direction: str = "both") -> dict[str, list[str]]:
        match direction:
            case "in" | "out" | "both":
                pass
            case _:
                raise StoreError("invalid link direction")
        unit = self.unit(unit_id)
        units = self.units
        outbound = unit.outbound_links()
        return {
            **(
                {
                    "out": sorted(x for x in outbound if x in units),
                    "out_unresolved": sorted(x for x in outbound if x not in units),
                }
                if direction in {"out", "both"}
                else {}
            ),
            **(
                {
                    "in": sorted(
                        u.id for u in units.values() if unit_id in u.outbound_links()
                    )
                }
                if direction in {"in", "both"}
                else {}
            ),
        }


def _read_unit(path: Path, root: Path) -> Unit:
    raw = path.read_text(encoding="utf-8")
    fields, body = _tsv(raw) if path.suffix == ".tsv" else parse_frontmatter(raw)
    return Unit(
        str(fields.get("id") or path.relative_to(root).with_suffix("").as_posix()),
        path,
        fields,
        body,
        raw,
        hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12],
    )
