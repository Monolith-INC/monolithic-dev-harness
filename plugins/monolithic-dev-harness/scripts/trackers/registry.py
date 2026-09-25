"""Discover and validate shipped and approval-pinned tracker manifests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from harness import state

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHIPPED_ROOT = PLUGIN_ROOT / "trackers"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "tracker.schema.json"
LEGACY_NAMES = {"azure_devops": "azure-devops", "local_tracker": "local"}


class TrackerError(ValueError):
    """A tracker selection or manifest cannot be used safely."""


@dataclass(frozen=True)
class Tracker:
    name: str
    manifest: Mapping[str, Any]
    root: Path
    source: str


@lru_cache(maxsize=1)
def _schema() -> Mapping[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _field(error: ValidationError) -> str:
    return ".".join(map(str, error.absolute_path)) or str(error.validator or "manifest")


def _invalid(field: str, message: str) -> TrackerError:
    return TrackerError(f"invalid tracker manifest at {field}: {message}")


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    error = next(
        iter(
            sorted(
                _validator().iter_errors(manifest),
                key=lambda item: list(item.absolute_path),
            )
        ),
        None,
    )
    match error:
        case None:
            return _validate_domain(dict(manifest))
        case ValidationError() as invalid:
            raise _invalid(_field(invalid), invalid.message)


def _validate_domain(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = tuple(manifest["artifacts"])
    names = tuple(str(item["name"]) for item in artifacts)
    graph = {
        str(item["name"]): tuple(map(str, item["children"])) for item in artifacts
    }
    roles = manifest["roles"]
    _require(len(names) == len(set(names)), "artifacts", "artifact names must be unique")
    _require(
        all(child in graph for children in graph.values() for child in children),
        "artifacts.children",
        "every child must name a declared artifact",
    )
    _require(
        not any(_has_cycle(graph, name, frozenset(), frozenset()) for name in graph),
        "artifacts",
        "artifact hierarchy contains a cycle",
    )
    _require(
        all(name in graph for name in (*roles["containers"], roles["delivery_unit"])),
        "roles",
        "every container and delivery_unit must name a declared artifact",
    )
    _require(roles["step"] in graph, "roles.step", "must name a declared artifact")
    _require(
        all(
            _reachable(graph, container, roles["delivery_unit"])
            for container in roles["containers"]
        ),
        "roles.containers",
        "every container must be above the delivery_unit",
    )
    _require(
        _reachable(graph, roles["delivery_unit"], roles["step"]),
        "roles.step",
        "step must be below delivery_unit",
    )
    return manifest


def _require(condition: bool, field: str, message: str) -> None:
    match condition:
        case True:
            return None
        case False:
            raise _invalid(field, message)


def _has_cycle(
    graph: Mapping[str, tuple[str, ...]],
    name: str,
    visiting: frozenset[str],
    visited: frozenset[str],
) -> bool:
    return name in visiting or (
        name not in visited
        and any(
            _has_cycle(graph, child, visiting | {name}, visited | {name})
            for child in graph[name]
        )
    )


def _reachable(graph: Mapping[str, tuple[str, ...]], start: str, target: str) -> bool:
    return start == target or any(
        _reachable(graph, child, target) for child in graph[start]
    )


def folder_digest(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in folder.rglob("*") if item.is_file()):
        digest.update(path.relative_to(folder).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def pin_approved_trackers(
    repo: Path, approval_id: str, folders: Iterable[Path]
) -> None:
    state.pin_trackers(
        repo,
        approval_id,
        {str(folder.resolve()): folder_digest(folder) for folder in folders},
    )


def _is_pinned(repo: Path, folder: Path) -> bool:
    return folder_digest(folder) in state.pinned_trackers(repo).get(
        str(folder.resolve()), set()
    )


def _manifest_paths(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.glob("*/tracker.json"))) if root.is_dir() else ()


@lru_cache(maxsize=256)
def _load(path: Path, mtime_ns: int, source: str) -> Tracker:
    del mtime_ns
    manifest = validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    return Tracker(str(manifest["name"]), manifest, path.parent, source)


def _load_path(path: Path, source: str) -> Tracker:
    try:
        return _load(path, path.stat().st_mtime_ns, source)
    except (OSError, json.JSONDecodeError, TrackerError) as exc:
        match exc:
            case TrackerError():
                raise exc
            case _:
                raise _invalid(str(path), str(exc)) from exc


def _discover(root: Path, source: str) -> tuple[Tracker, ...]:
    return tuple(_load_path(path, source) for path in _manifest_paths(root))


def _onboarded(repo: Path) -> tuple[Tracker, ...]:
    return tuple(
        tracker
        for tracker in _discover(repo / ".harness" / "trackers", "onboarded")
        if tracker.manifest.get("status") == "approved" and _is_pinned(repo, tracker.root)
    )


def available(
    repo: Path, *, shipped_root: Path = DEFAULT_SHIPPED_ROOT
) -> tuple[Tracker, ...]:
    return tuple(
        sorted(
            (*_discover(shipped_root, "shipped"), *_onboarded(repo)),
            key=lambda tracker: (tracker.name, tracker.source),
        )
    )


def approved_onboarded_trackers(repo: Path) -> tuple[Path, ...]:
    return tuple(
        tracker.root
        for tracker in _discover(repo / ".harness" / "trackers", "onboarded")
        if tracker.manifest.get("status") == "approved"
    )


def _selection(repo: Path) -> tuple[str, str]:
    path = repo / ".harness" / "integrations.json"
    path = repo / ".codex-workflows" / "integrations.json" if not path.is_file() else path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrackerError(f"could not read tracker selection: {exc}") from exc
    tracker = payload.get("tracker") if isinstance(payload, dict) else None
    match tracker:
        case {"name": str(name), "source": str(source)}:
            return name, source
        case {"name": str(name)}:
            return name, "shipped"
        case {"adapter": str(adapter)}:
            return LEGACY_NAMES.get(adapter, adapter), "shipped"
        case _:
            raise TrackerError(
                "tracker selection requires tracker.name or legacy tracker.adapter"
            )


def active(repo: Path, *, shipped_root: Path = DEFAULT_SHIPPED_ROOT) -> Tracker:
    name, source = _selection(repo)
    matches = tuple(
        tracker
        for tracker in available(repo, shipped_root=shipped_root)
        if tracker.name == name and tracker.source == source
    )
    match matches:
        case (tracker,):
            return tracker
        case ():
            raise TrackerError(
                f"active tracker {name!r} ({source}) is missing, invalid, or not approved"
            )
        case _:
            raise TrackerError(f"active tracker {name!r} ({source}) is ambiguous")
