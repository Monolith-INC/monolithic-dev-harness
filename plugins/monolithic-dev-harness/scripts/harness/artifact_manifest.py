"""A compact reading map for the prepared bundle; file reads are isolated here."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from core.result import Result, attempt, bind, err, fmap, require, sequence


def document(repo: Path, encoded: str) -> Result[dict[str, str]]:
    return bind(
        attempt(
            lambda: json.loads(encoded),
            "manifest_invalid",
            "document entry",
            ValueError,
        ),
        lambda entry: _document(repo, entry),
    )


def _document(repo: Path, entry: object) -> Result[dict[str, str]]:
    match entry:
        case {
            "path": str() as path,
            "purpose": str() as purpose,
            "read_when": str() as trigger,
            "owner": str() as owner,
        } if all((path, purpose, trigger, owner)):
            return bind(
                require(
                    (repo / path).resolve().is_relative_to(repo.resolve())
                    and (repo / path).is_file(),
                    "manifest_invalid",
                    "each document must be an existing file inside the project",
                ),
                lambda _: fmap(
                    attempt(
                        lambda: (repo / path).read_bytes(),
                        "manifest_unreadable",
                        path,
                        OSError,
                    ),
                    lambda content: {
                        "path": (repo / path)
                        .resolve()
                        .relative_to(repo.resolve())
                        .as_posix(),
                        "purpose": purpose,
                        "read_when": trigger,
                        "owner": owner,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    },
                ),
            )
        case _:
            return err(
                "manifest_invalid",
                "each entry needs path, purpose, read_when and owner",
            )


def render(repo: Path, entries: tuple[str, ...]) -> Result[str]:
    return bind(
        require(bool(entries), "manifest_invalid", "at least one document is required"),
        lambda _: fmap(
            sequence(document(repo, entry) for entry in entries),
            lambda documents: (
                "# Prepared artifact manifest\n\n"
                "Read only the documents relevant to the current decision. Recheck hashes before execution.\n\n"
                "```json\n"
                + json.dumps(
                    {"version": 1, "documents": documents}, indent=2, ensure_ascii=False
                )
                + "\n```\n"
            ),
        ),
    )


def save(repo: Path, target: str, entries: tuple[str, ...]) -> Result[str]:
    return bind(
        require(
            bool(target)
            and (repo / target).resolve().is_relative_to(repo.resolve())
            and Path(target).suffix.lower() == ".md",
            "manifest_invalid",
            "save the manifest as a Markdown file inside the project",
        ),
        lambda _: bind(
            render(repo, entries),
            lambda content: fmap(
                attempt(
                    lambda: _write(repo / target, content),
                    "manifest_unwritable",
                    target,
                    OSError,
                ),
                lambda _: content,
            ),
        ),
    )


def _write(target: Path, content: str) -> Path:
    """Atomic filesystem edge; unique temporary storage is cleaned on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as folder:
        match Path(folder) / "manifest.md":
            case temporary:
                temporary.write_text(content, encoding="utf-8")
                return temporary.replace(target)
