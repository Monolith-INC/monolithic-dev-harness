"""Immutable, project-agnostic knowledge stores owned by the harness.

Stores live under ``.harness/knowledge/stores/<store-id>``.  The catalog and
source index are rebuildable views; revisions and lifecycle events are
append-only evidence records.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.config import POLICY_RELATIVE_PATH, load_policy

KNOWLEDGE = Path(".harness") / "knowledge"
SCHEMA = "harness-knowledge-store/v1"
STORE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
MAX_FIND_HITS = 12


class KnowledgeError(ValueError):
    """A knowledge store cannot be read or updated safely."""


@dataclass(frozen=True)
class StorePaths:
    root: Path
    manifest: Path
    catalog: Path
    source_index: Path
    revisions: Path
    events: Path


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode()).hexdigest()}"


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _paths(repo: Path, store_id: str) -> StorePaths:
    if not STORE_ID_RE.fullmatch(store_id):
        raise KnowledgeError("store id must be lowercase letters, digits, and hyphens")
    root = repo / KNOWLEDGE / "stores" / store_id
    return StorePaths(
        root=root,
        manifest=root / "manifest.json",
        catalog=root / "catalog.json",
        source_index=root / "source-index.json",
        revisions=root / "revisions",
        events=root / "events",
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise KnowledgeError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest(store_id: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "store_id": store_id,
        "immutable_revisions": True,
        "evidence_required": True,
        "source_index_required": True,
        "query": {"max_find_hits": MAX_FIND_HITS, "default_freshness": "fresh_only"},
    }


def _empty_catalog(store_id: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "store_id": store_id, "units": {}}


def _empty_index(store_id: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "store_id": store_id, "sources": {}}


def _ensure_store(repo: Path, store_id: str) -> StorePaths:
    paths = _paths(repo, store_id)
    match paths.manifest.exists():
        case True:
            manifest = _read_json(paths.manifest)
            if manifest.get("schema") != SCHEMA or manifest.get("store_id") != store_id:
                raise KnowledgeError(
                    f"{paths.manifest} is not a compatible knowledge store"
                )
        case False:
            _write_json(paths.manifest, _manifest(store_id))
            _write_json(paths.catalog, _empty_catalog(store_id))
            _write_json(paths.source_index, _empty_index(store_id))
            paths.revisions.mkdir(parents=True, exist_ok=True)
            paths.events.mkdir(parents=True, exist_ok=True)
    return paths


def _policy_revision(repo: Path) -> dict[str, Any]:
    policy_path = repo / POLICY_RELATIVE_PATH
    if not policy_path.is_file():
        raise KnowledgeError(
            f"{POLICY_RELATIVE_PATH} is required before knowledge initialization"
        )
    policy = load_policy(repo)
    payload = {
        "logical_unit_id": "project/harness-policy",
        "title": "Harness policy",
        "tier": "structure",
        "area": "harness-policy",
        "kind": "fact",
        "content": {
            "summary": "The harness policy is the repository's operational routing contract.",
            "policy": policy,
            "open_questions": [],
        },
        "evidence": [
            {
                "kind": "repository_file",
                "locator": str(POLICY_RELATIVE_PATH),
                "fingerprint": {"sha256": _file_digest(policy_path)},
            }
        ],
        "provenance": {
            "method": "harness-policy-seed/v1",
            "confidence": "source_backed",
        },
        "lineage": {"supersedes": [], "related": []},
        "retrieval": {
            "read_when": [
                "routing a task through harness-governed repository boundaries",
                "selecting checks, generated paths, or workflow configuration",
            ],
            "keywords": ["harness", "policy", "repository", "checks", "workflow"],
        },
    }
    return {**payload, "revision_id": _digest(payload)}


def _write_revision(paths: StorePaths, revision: Mapping[str, Any]) -> bool:
    revision_id = str(revision["revision_id"])
    path = paths.revisions / f"{revision_id.removeprefix('sha256:')}.json"
    match path.exists():
        case True:
            return False
        case False:
            _write_json(path, revision)
            return True


def _event(paths: StorePaths, payload: Mapping[str, Any]) -> str:
    event_id = _digest(payload)
    _write_json(
        paths.events / f"{event_id.removeprefix('sha256:')}.json",
        {**payload, "event_id": event_id},
    )
    return event_id


def _catalog(paths: StorePaths) -> dict[str, Any]:
    catalog = _read_json(paths.catalog)
    if catalog.get("schema") != SCHEMA or not isinstance(catalog.get("units"), dict):
        raise KnowledgeError(f"{paths.catalog} is not a compatible catalog")
    return catalog


def _index_revision(
    index: dict[str, Any], revision: Mapping[str, Any]
) -> dict[str, Any]:
    sources = index.get("sources", {})
    mappings = tuple(
        (f"{item.get('kind')}:{item.get('locator')}", str(revision["revision_id"]))
        for item in revision.get("evidence", [])
        if isinstance(item, dict) and item.get("kind") and item.get("locator")
    )
    return {
        **index,
        "sources": {
            **sources,
            **{
                key: sorted(set((*sources.get(key, []), revision_id)))
                for key, revision_id in mappings
            },
        },
    }


def initialize(repo: Path, store_id: str = "project") -> dict[str, Any]:
    paths = _ensure_store(repo.resolve(), store_id)
    return refresh(repo.resolve(), store_id, paths)


def refresh(
    repo: Path, store_id: str = "project", paths: StorePaths | None = None
) -> dict[str, Any]:
    active_paths = paths or _ensure_store(repo.resolve(), store_id)
    revision = _policy_revision(repo.resolve())
    catalog = _catalog(active_paths)
    units = catalog["units"]
    logical_id = str(revision["logical_unit_id"])
    existing = units.get(logical_id, {})
    current = existing.get("current")
    match current == revision["revision_id"]:
        case True:
            return {"outcome": "unchanged", "store": store_id, "revision": current}
        case False:
            _write_revision(active_paths, revision)
            statuses = {
                **existing.get("revisions", {}),
                str(revision["revision_id"]): "current",
            }
            previous_statuses = {
                **statuses,
                **({str(current): "stale"} if current else {}),
            }
            updated_catalog = {
                **catalog,
                "units": {
                    **units,
                    logical_id: {
                        "current": revision["revision_id"],
                        "revisions": previous_statuses,
                    },
                },
            }
            _write_json(active_paths.catalog, updated_catalog)
            index = _index_revision(_read_json(active_paths.source_index), revision)
            _write_json(active_paths.source_index, index)
            event = _event(
                active_paths,
                {
                    "type": "revision_created" if current is None else "source_changed",
                    "logical_unit_id": logical_id,
                    "previous_revision": current,
                    "current_revision": revision["revision_id"],
                },
            )
            return {
                "outcome": "created" if current is None else "refreshed",
                "store": store_id,
                "revision": revision["revision_id"],
                "event": event,
            }


def _current_revisions(paths: StorePaths) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            logical_id,
            str(entry.get("current", "")),
            str(entry.get("revisions", {}).get(entry.get("current"), "")),
        )
        for logical_id, entry in _catalog(paths)["units"].items()
        if isinstance(entry, dict) and entry.get("current")
    )


def _revision_path(paths: StorePaths, revision_id: str) -> Path:
    return paths.revisions / f"{revision_id.removeprefix('sha256:')}.json"


def _load_revision(paths: StorePaths, revision_id: str) -> dict[str, Any]:
    path = _revision_path(paths, revision_id)
    if not path.is_file():
        raise KnowledgeError(f"unknown revision: {revision_id}")
    revision = _read_json(path)
    if revision.get("revision_id") != revision_id:
        raise KnowledgeError(f"revision identity mismatch: {revision_id}")
    return revision


def catalog(repo: Path, store_id: str = "project") -> tuple[dict[str, Any], ...]:
    paths = _paths(repo.resolve(), store_id)
    return tuple(
        {
            "logical_unit_id": logical_id,
            "revision_id": revision_id,
            "status": status,
            "title": _load_revision(paths, revision_id).get("title", logical_id),
            "tier": _load_revision(paths, revision_id).get("tier", ""),
            "area": _load_revision(paths, revision_id).get("area", ""),
            "read_when": _load_revision(paths, revision_id)
            .get("retrieval", {})
            .get("read_when", []),
        }
        for logical_id, revision_id, status in _current_revisions(paths)
    )


def _flatten(value: object) -> str:
    match value:
        case str() as text:
            return text
        case Mapping() as mapping:
            return " ".join(_flatten(item) for item in mapping.values())
        case Iterable() as values:
            return " ".join(_flatten(item) for item in values)
        case _:
            return str(value)


def find(
    repo: Path, terms: Sequence[str], store_id: str = "project"
) -> tuple[dict[str, Any], ...]:
    normalized = tuple(term.lower() for term in terms if term.strip())
    if not normalized:
        raise KnowledgeError("find needs at least one term")
    paths = _paths(repo.resolve(), store_id)
    matches = tuple(
        (
            sum(text.count(term) for term in normalized),
            logical_id,
            revision_id,
            revision,
        )
        for logical_id, revision_id, status in _current_revisions(paths)
        for revision in (_load_revision(paths, revision_id),)
        for text in (_flatten(revision).lower(),)
        if status == "current" and all(term in text for term in normalized)
    )
    return tuple(
        {
            "logical_unit_id": logical_id,
            "revision_id": revision_id,
            "title": revision.get("title", logical_id),
            "matched_terms": list(normalized),
            "summary": revision.get("content", {}).get("summary", ""),
        }
        for _, logical_id, revision_id, revision in sorted(
            matches, key=lambda item: (-item[0], item[1])
        )[:MAX_FIND_HITS]
    )


def resolve(repo: Path, logical_id: str, store_id: str = "project") -> dict[str, Any]:
    paths = _paths(repo.resolve(), store_id)
    entry = _catalog(paths)["units"].get(logical_id)
    if not isinstance(entry, dict) or not entry.get("current"):
        raise KnowledgeError(f"unknown logical unit: {logical_id}")
    revision_id = str(entry["current"])
    return {
        "logical_unit_id": logical_id,
        "revision_id": revision_id,
        "status": entry.get("revisions", {}).get(revision_id, "unverifiable"),
    }


def fetch(repo: Path, address: str, store_id: str = "project") -> dict[str, Any]:
    logical_id, separator, revision_id = address.partition("@")
    resolved = resolve(repo, logical_id, store_id)
    target = revision_id if separator else resolved["revision_id"]
    revision = _load_revision(_paths(repo.resolve(), store_id), target)
    if revision.get("logical_unit_id") != logical_id:
        raise KnowledgeError(f"{target} does not belong to {logical_id}")
    return {
        **revision,
        "status": resolved["status"]
        if target == resolved["revision_id"]
        else "superseded",
    }


def status(repo: Path, store_id: str = "project") -> dict[str, Any]:
    paths = _paths(repo.resolve(), store_id)
    revisions = tuple(
        state
        for entry in _catalog(paths)["units"].values()
        if isinstance(entry, dict)
        for state in entry.get("revisions", {}).values()
    )
    return {
        "store": store_id,
        "units": len(_catalog(paths)["units"]),
        "current": revisions.count("current"),
        "stale": revisions.count("stale"),
        "events": len(tuple(paths.events.glob("*.json"))),
    }
