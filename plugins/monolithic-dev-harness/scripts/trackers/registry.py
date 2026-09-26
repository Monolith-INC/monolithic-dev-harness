"""Discover and validate shipped and approval-pinned tracker manifests."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from harness import state

from .schema_check import SchemaError, errors, unsupported

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHIPPED_ROOT = PLUGIN_ROOT / "trackers"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "tracker.schema.json"
# A tracker name is also a folder name: checked whole, since `$` in the schema allows "x\n".
NAME = re.compile(r"[a-z][a-z0-9-]{0,63}")

# The one table between tracker manifest names and the adapter ids integrations.json has used.
ADAPTER_IDS = {
    "azure-devops": "azure_devops",
    "linear": "linear",
    "local": "local_tracker",
}


def adapter_id(name: str) -> str:
    """The integrations adapter id for a tracker manifest name."""
    return ADAPTER_IDS.get(name, name)


def tracker_name(adapter: str) -> str:
    """The tracker manifest name for a legacy integrations adapter id."""
    return {value: key for key, value in ADAPTER_IDS.items()}.get(adapter, adapter)


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
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    match sorted(unsupported(schema)):
        case []:
            return schema
        case unknown:
            raise TrackerError(
                f"tracker schema uses keywords the checker does not support: {unknown}"
            )


def _field(error: SchemaError) -> str:
    return ".".join(map(str, error.path)) or error.keyword


def _invalid(field: str, message: str) -> TrackerError:
    return TrackerError(f"invalid tracker manifest at {field}: {message}")


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    error = next(
        iter(
            sorted(
                errors(manifest, _schema()),
                key=lambda item: tuple(map(str, item.path)),
            )
        ),
        None,
    )
    match error:
        case None:
            return _validate_domain(dict(manifest))
        case SchemaError() as invalid:
            raise _invalid(_field(invalid), invalid.message)


def _validate_domain(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = tuple(manifest["artifacts"])
    names = tuple(str(item["name"]) for item in artifacts)
    graph = {str(item["name"]): tuple(map(str, item["children"])) for item in artifacts}
    roles = manifest["roles"]
    _require(
        len(names) == len(set(names)), "artifacts", "artifact names must be unique"
    )
    _require(
        all(child in graph for children in graph.values() for child in children),
        "artifacts.children",
        "every child must name a declared artifact",
    )
    _require(
        _is_acyclic(graph),
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
            roles["delivery_unit"] in _descendants(graph, container)
            for container in roles["containers"]
        ),
        "roles.containers",
        "every container must be above the delivery_unit",
    )
    _require(
        roles["step"] in _descendants(graph, roles["delivery_unit"]),
        "roles.step",
        "step must be below delivery_unit",
    )
    _require(
        bool(NAME.fullmatch(manifest["name"])),
        "name",
        "must be a lowercase tracker name",
    )
    _validate_ids(manifest["ids"])
    return manifest


def _validate_ids(ids: Mapping[str, Any]) -> None:
    """Id patterns are spliced into the hook's regexes: they must compile and capture nothing."""
    for key in ("pattern", "branch_key"):
        try:
            groups = re.compile(ids[key]).groups
        except re.error as exc:
            raise _invalid(
                f"ids.{key}", f"is not a valid regular expression: {exc}"
            ) from exc
        _require(
            groups == 0, f"ids.{key}", "must not contain capturing groups; use (?:...)"
        )
    _require(
        all(template.count("{id}") == 1 for template in ids["mention"]),
        "ids.mention",
        "every mention form must contain {id} exactly once",
    )


def _require(condition: bool, field: str, message: str) -> None:
    match condition:
        case True:
            return None
        case False:
            raise _invalid(field, message)


def _is_acyclic(graph: Mapping[str, tuple[str, ...]]) -> bool:
    """Kahn's algorithm: the hierarchy is acyclic when every artifact can be peeled off."""
    parents = {name: 0 for name in graph}
    for children in graph.values():
        for child in children:
            parents[child] += 1
    ready = [name for name, count in parents.items() if count == 0]
    peeled = 0
    while ready:
        name = ready.pop()
        peeled += 1
        for child in graph[name]:
            parents[child] -= 1
            if parents[child] == 0:
                ready.append(child)
    return peeled == len(graph)


def _descendants(graph: Mapping[str, tuple[str, ...]], start: str) -> frozenset[str]:
    """`start` and every artifact below it, each visited once."""
    seen = {start}
    pending = [start]
    while pending:
        for child in graph[pending.pop()]:
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return frozenset(seen)


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


def _valid_onboarded(repo: Path) -> tuple[Tracker, ...]:
    """Onboarded manifests that validate. A broken one hides only itself, never the registry."""
    return tuple(
        tracker
        for tracker in map(
            _try_load_onboarded, _manifest_paths(repo / ".harness" / "trackers")
        )
        if tracker is not None and tracker.manifest.get("status") == "approved"
    )


@dataclass(frozen=True)
class OnboardedStatus:
    """What one onboarded folder is: `invalid`, `draft`, `unpinned`, or `pinned`."""

    folder: Path
    state: str
    detail: str = ""


def onboarded_status(repo: Path) -> tuple[OnboardedStatus, ...]:
    """Every folder under `.harness/trackers/`, for `harness doctor` to report."""
    return tuple(
        map(
            lambda path: _status(repo, path),
            _manifest_paths(repo / ".harness" / "trackers"),
        )
    )


def _status(repo: Path, path: Path) -> OnboardedStatus:
    try:
        tracker = _load_path(path, "onboarded")
    except TrackerError as exc:
        return OnboardedStatus(path.parent, "invalid", str(exc))
    match (tracker.manifest.get("status"), _is_pinned(repo, tracker.root)):
        case ("approved", True):
            return OnboardedStatus(path.parent, "pinned")
        case ("approved", False):
            return OnboardedStatus(path.parent, "unpinned")
        case _:
            return OnboardedStatus(path.parent, "draft")


def _try_load_onboarded(path: Path) -> Tracker | None:
    try:
        return _load_path(path, "onboarded")
    except TrackerError:
        return None


def _onboarded(repo: Path) -> tuple[Tracker, ...]:
    return tuple(
        tracker for tracker in _valid_onboarded(repo) if _is_pinned(repo, tracker.root)
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


def approved_onboarded_trackers(repo: Path, approval_text: str) -> tuple[Path, ...]:
    """Folders the user's approval names: the word "tracker" and the tracker's own name.

    An approval for something else (a push, a work item) never pins a tracker folder.
    """
    return (
        tuple(
            tracker.root
            for tracker in _valid_onboarded(repo)
            if re.search(
                rf"(?<![\w-]){re.escape(tracker.name)}(?![\w-])",
                approval_text,
                re.IGNORECASE,
            )
        )
        if re.search(r"\btrackers?\b", approval_text, re.IGNORECASE)
        else ()
    )


def _selection_path(repo: Path) -> Path:
    path = repo / ".harness" / "integrations.json"
    return (
        repo / ".codex-workflows" / "integrations.json" if not path.is_file() else path
    )


def is_selected(repo: Path) -> bool:
    """Whether the repository chooses a tracker at all (an unreadable choice still counts)."""
    try:
        payload = json.loads(_selection_path(repo).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, json.JSONDecodeError):
        return True
    return not isinstance(payload, dict) or "tracker" in payload


def _selection(repo: Path) -> tuple[str, str]:
    try:
        payload = json.loads(_selection_path(repo).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrackerError(f"could not read tracker selection: {exc}") from exc
    tracker = payload.get("tracker") if isinstance(payload, dict) else None
    match tracker:
        case {"name": str(name), "source": str(source)}:
            return name, source
        case {"name": str(name)}:
            return name, "shipped"
        case {"adapter": str(adapter)}:
            return tracker_name(adapter), "shipped"
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
