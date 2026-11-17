"""Explicit, non-destructive migration from a legacy JSON knowledge store.

Migration copies the original bytes into a non-indexed archive and publishes a
new directory only after verifying the source did not change. Existing paths
are never replaced. No command invokes this operation implicitly.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_knowledge import store

from core.result import Result, attempt

_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
_UNIT_ID = re.compile(r"^[0-9a-z][0-9a-z._/-]*$")
_SCHEMA = "harness-knowledge-store/v1"
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1


@dataclass(frozen=True)
class FileSnapshot:
    path: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
class MigratedUnit:
    legacy_id: str
    identifier: str
    revision_id: str
    content: str


@dataclass(frozen=True)
class MigrationResult:
    destination: str
    files: int
    units: int


def _snapshot(source: Path) -> tuple[FileSnapshot, ...]:
    paths = tuple(sorted(source.rglob("*")))
    match tuple(path for path in paths if path.is_symlink()):
        case ():
            return tuple(
                FileSnapshot(
                    str(path.relative_to(source)),
                    content,
                    hashlib.sha256(content).hexdigest(),
                )
                for path in paths
                if path.is_file()
                for content in (path.read_bytes(),)
            )
        case _:
            raise ValueError(
                "legacy stores containing symbolic links cannot be migrated"
            )


def _json(files: tuple[FileSnapshot, ...], path: str) -> dict[str, Any]:
    match tuple(item.content for item in files if item.path == path):
        case (content,):
            value = json.loads(content)
            match value:
                case dict():
                    return value
                case _:
                    raise ValueError(f"{path} is not a JSON object")
        case _:
            raise ValueError(f"missing legacy file: {path}")


def _one_line(value: object) -> str:
    return " ".join(str(value).split())


def _source(item: object) -> str | None:
    match item:
        case {
            "kind": "repository_file",
            "locator": str() as locator,
            "fingerprint": {"sha256": str() as fingerprint},
        } if (digest := re.sub(r"^sha256:", "", fingerprint)) and re.fullmatch(
            r"[0-9a-f]{64}", digest
        ):
            return f"{locator}#sha256:{digest}"
        case {"locator": str() as locator}:
            return _one_line(locator)
        case _:
            return None


def _unit(files: tuple[FileSnapshot, ...], legacy_id: str, entry: Any) -> MigratedUnit:
    match entry:
        case {"current": str() as revision_id, "revisions": dict() as statuses} if (
            _REVISION.fullmatch(revision_id)
        ):
            revision = _json(files, f"revisions/{revision_id[7:]}.json")
            payload = {
                key: value for key, value in revision.items() if key != "revision_id"
            }
            canonical = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            digest = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            match revision:
                case {"revision_id": stored_id, "logical_unit_id": stored_unit} if (
                    stored_id == revision_id
                    and stored_unit == legacy_id
                    and digest == revision_id
                ):
                    return _render_unit(legacy_id, revision_id, statuses, revision)
                case _:
                    raise ValueError(f"revision identity does not match {legacy_id}")
        case _:
            raise ValueError(f"invalid catalog entry for {legacy_id}")


def _render_unit(
    legacy_id: str, revision_id: str, statuses: dict[str, Any], revision: dict[str, Any]
) -> MigratedUnit:
    match (
        bool(_UNIT_ID.fullmatch(legacy_id))
        and ".." not in legacy_id.split("/")
        and legacy_id.split("/")[-1] != "manifest"
    ):
        case False:
            raise ValueError(f"legacy id cannot be preserved: {legacy_id}")
        case True:
            pass
    identifier = legacy_id
    provenance = revision.get("provenance", {})
    derived = (
        isinstance(provenance, dict)
        and provenance.get("method") == "harness-settings-seed/v1"
        and bool(revision.get("evidence"))
    )
    match derived:
        case False:
            raise ValueError(
                f"legacy provenance requires a reviewed mapping: {legacy_id}"
            )
        case True:
            pass
    retrieval = (
        revision.get("retrieval") if isinstance(revision.get("retrieval"), dict) else {}
    )
    read_when = (
        retrieval.get("read_when")
        if isinstance(retrieval.get("read_when"), list)
        else []
    )
    evidence = (
        revision.get("evidence") if isinstance(revision.get("evidence"), list) else []
    )
    fields = {
        "id": identifier,
        "title": _one_line(revision.get("title", legacy_id)),
        "type": _one_line(revision.get("tier", "structure")),
        "area": _one_line(revision.get("area", "")),
        "provenance": "derived" if derived else "assumed",
        "status": "current" if statuses.get(revision_id) == "current" else "deprecated",
        "read_when": "; ".join(_one_line(item) for item in read_when),
        "sources": tuple(
            source for source in map(_source, evidence) if source is not None
        ),
        "legacy_id": _one_line(legacy_id),
        "legacy_revision": revision_id,
    }
    encoded = json.dumps(revision, ensure_ascii=False, indent=2, sort_keys=True)
    body = (
        "## Preserved legacy revision\n\n"
        + "\n".join("    " + line for line in encoded.splitlines())
        + "\n"
    )
    return MigratedUnit(
        legacy_id, identifier, revision_id, store.dump_frontmatter(fields) + "\n" + body
    )


def _units(files: tuple[FileSnapshot, ...]) -> tuple[MigratedUnit, ...]:
    manifest = _json(files, "manifest.json")
    catalog = _json(files, "catalog.json")
    match manifest, catalog:
        case {"schema": first}, {"schema": second, "units": dict() as entries} if (
            first == _SCHEMA and second == _SCHEMA
        ):
            return tuple(
                _unit(files, str(key), value) for key, value in sorted(entries.items())
            )
        case _:
            raise ValueError("legacy knowledge manifest or catalog is invalid")


def _write_file(root: Path, relative: str, content: bytes) -> int:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    return target.write_bytes(content)


def _publish(source: Path, destination: Path) -> None:
    """Use the operating system's no-replace rename; fail closed if unsupported."""
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise OSError(
            errno.ENOTSUP, "atomic no-replace directory rename unavailable"
        ) from exc
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    match rename(
        _AT_FDCWD,
        os.fsencode(source),
        _AT_FDCWD,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    ):
        case 0:
            return
        case _:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number), str(destination))


def _migrate(source: Path, destination: Path) -> MigrationResult:
    source = source.resolve(strict=True)
    destination = destination.parent.resolve(strict=True) / destination.name
    match (
        destination.exists()
        or destination.is_symlink()
        or destination.is_relative_to(source)
        or source.is_relative_to(destination)
    ):
        case True:
            raise ValueError("destination already exists or is inside the legacy store")
        case False:
            pass
    files = _snapshot(source)
    units = _units(files)
    mapping = {
        "schema": "harness-knowledge-migration/v1",
        "legacy_files": {item.path: item.sha256 for item in files},
        "units": {
            item.legacy_id: {"id": item.identifier, "revision_id": item.revision_id}
            for item in units
        },
    }
    with tempfile.TemporaryDirectory(
        prefix=".knowledge-migration-", dir=destination.parent
    ) as temporary:
        staged = Path(temporary) / "store"
        staged.mkdir()
        tuple(
            _write_file(staged, ".legacy/" + item.path, item.content) for item in files
        )
        tuple(
            _write_file(staged, item.identifier + ".md", item.content.encode("utf-8"))
            for item in units
        )
        _write_file(
            staged,
            "migration-manifest.json",
            json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True).encode(
                "utf-8"
            ),
        )
        copied = _snapshot(staged / ".legacy")
        indexed = store.KnowledgeStore(staged).units
        verified = (
            _snapshot(source) == files
            and copied == files
            and set(indexed) == {item.identifier for item in units}
            and all(indexed[item.identifier].raw == item.content for item in units)
        )
        match verified:
            case False:
                raise ValueError("legacy store changed during migration; retry")
            case True:
                _publish(staged, destination)
    return MigrationResult(str(destination), len(files), len(units))


def migrate(source: Path, destination: Path) -> Result[MigrationResult]:
    return attempt(
        lambda: _migrate(source, destination),
        "knowledge_migration_failed",
        "Could not migrate the legacy knowledge store",
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        store.StoreError,
    )
