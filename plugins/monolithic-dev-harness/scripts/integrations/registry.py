"""Find tracker folders, check them against the contract, and say which one the repository uses.

Shipped trackers live in the plugin's `trackers/`; onboarded ones in the repository's
`.harness/trackers/`, and count only while the folder still matches the digest the user trusted.
Each folder is checked on its own: a broken one is reported and never hides the others.
"""

from __future__ import annotations

import json
import re
import string
import types
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from core.result import (
    Err,
    Failure,
    Ok,
    Result,
    attempt,
    bind,
    err,
    failures,
    fmap,
    oks,
    require,
    sequence,
    value_or,
)
from core.schema import load_schema, validate
from harness.settings import Selection, Settings

from . import trust
from .contracts import (
    AdapterContext,
    Artifact,
    IdRules,
    LogicalState,
    Manifest,
    PlanningReply,
    TrackerOps,
    Transport,
    WorkItemKind,
    WriteRules,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_ROOT = PLUGIN_ROOT / "trackers"
ONBOARDED_RELATIVE_PATH = Path(".harness") / "trackers"
SCHEMA_PATH = PLUGIN_ROOT / "config" / "tracker.schema.json"
MANIFEST = "tracker.json"
ADAPTER = "adapter.py"
BUILTIN_PLACEHOLDERS = frozenset({"plugin_root", "repo"})
# The hierarchy the harness workflow walks: each pair is (container kind, kind it must contain).
REQUIRED_CHILDREN = (
    (WorkItemKind.EPIC, WorkItemKind.FEATURE),
    (WorkItemKind.FEATURE, WorkItemKind.USER_STORY),
    (WorkItemKind.FEATURE, WorkItemKind.BUG),
    (WorkItemKind.USER_STORY, WorkItemKind.TASK),
)


@dataclass(frozen=True)
class NotConfigured:
    reason: str


@dataclass(frozen=True)
class Active:
    manifest: Manifest
    values: Mapping[str, str]


@dataclass(frozen=True)
class Invalid:
    failure: Failure


Resolution = NotConfigured | Active | Invalid


# --- reading one folder ---------------------------------------------------------------------


def read_manifest(folder: Path, source: str) -> Result[Manifest]:
    """The folder's manifest, checked against the schema and the harness's own rules.

    Checked once per process for each version of the folder's manifest and adapter.
    """
    return _read_manifest(
        folder, source, _stamp(folder / MANIFEST), _stamp(folder / ADAPTER)
    )


def _stamp(file: Path) -> tuple[int, int]:
    return value_or(
        attempt(
            lambda: (file.stat().st_mtime_ns, file.stat().st_size),
            "absent",
            str(file),
            OSError,
        ),
        (0, 0),
    )


@lru_cache(maxsize=64)
def _read_manifest(
    folder: Path,
    source: str,
    manifest_stamp: tuple[int, int],
    adapter_stamp: tuple[int, int],
) -> Result[Manifest]:
    return _labelled(
        folder,
        bind(
            bind(
                bind(_json(folder / MANIFEST), _conforming),
                lambda document: fmap(
                    _consistent(folder, document), lambda _: document
                ),
            ),
            lambda document: Ok(_manifest(folder, source, document)),
        ),
    )


def _labelled(folder: Path, result: Result[Manifest]) -> Result[Manifest]:
    match result:
        case Err(failure):
            return err(
                "invalid_tracker", f"tracker folder {folder.name!r}: {failure.message}"
            )
        case Ok() as kept:
            return kept


def _json(file: Path) -> Result[Any]:
    return attempt(
        lambda: json.loads(file.read_text(encoding="utf-8")),
        "invalid_tracker",
        f"{file.name} could not be read",
        OSError,
        ValueError,
    )


def _conforming(document: Any) -> Result[Mapping[str, Any]]:
    return bind(
        load_schema(SCHEMA_PATH),
        lambda schema: validate(schema, document, "tracker manifest"),
    )


def _consistent(folder: Path, document: Mapping[str, Any]) -> Result[None]:
    artifacts = {
        str(item["name"]): tuple(map(str, item["children"]))
        for item in document["artifacts"]
    }
    kinds = document["kinds"]
    settings = tuple(str(item["key"]) for item in document["settings"])
    replies = tuple(str(item["key"]) for item in document["planning"]["replies"])
    return bind(
        sequence(
            (
                require(
                    (folder / ADAPTER).is_file(),
                    "invalid_tracker",
                    f"the folder has no {ADAPTER}",
                ),
                require(
                    len(artifacts) == len(document["artifacts"]),
                    "invalid_tracker",
                    "artifact names must be unique",
                ),
                require(
                    all(
                        child in artifacts
                        for children in artifacts.values()
                        for child in children
                    ),
                    "invalid_tracker",
                    "every artifact child must name a declared artifact",
                ),
                require(
                    _acyclic(artifacts, frozenset(artifacts)),
                    "invalid_tracker",
                    "the artifact hierarchy contains a cycle",
                ),
                require(
                    all(name in artifacts for name in kinds.values()),
                    "invalid_tracker",
                    "every kind must name a declared artifact",
                ),
                require(
                    all(
                        kinds[child.value] in artifacts.get(kinds[parent.value], ())
                        for parent, child in REQUIRED_CHILDREN
                    ),
                    "invalid_tracker",
                    "artifacts must let an epic hold features, a feature hold user stories and bugs, "
                    "and a user story hold tasks",
                ),
                require(
                    len(set(settings)) == len(settings),
                    "invalid_tracker",
                    "setting keys must be unique",
                ),
                require(
                    len(set(replies)) == len(replies),
                    "invalid_tracker",
                    "planning reply keys must be unique",
                ),
                _placeholders(document["connection"], frozenset(settings)),
            )
        ),
        lambda _: _expressions(document["ids"]),
    )


def _acyclic(graph: Mapping[str, tuple[str, ...]], nodes: frozenset[str]) -> bool:
    """Whether the graph has no cycle: peel off the types that contain nothing left, layer by layer.

    Each layer costs one pass over the edges, so a wide or diamond-shaped hierarchy stays cheap.
    """
    leaves = frozenset(node for node in nodes if not set(graph.get(node, ())) & nodes)
    return not nodes or (bool(leaves) and _acyclic(graph, nodes - leaves))


def placeholders(text: str) -> frozenset[str]:
    return frozenset(
        field for _, field, _, _ in string.Formatter().parse(text) if field
    )


def _placeholders(
    connection: Mapping[str, Any], settings: frozenset[str]
) -> Result[None]:
    used = frozenset(
        name for arg in connection.get("args", ()) for name in placeholders(arg)
    )
    unknown = used - settings - BUILTIN_PLACEHOLDERS
    return require(
        not unknown,
        "invalid_tracker",
        f"connection uses undeclared values {sorted(unknown)}",
    )


def _compiles(expression: str, what: str) -> Result[re.Pattern[str]]:
    return attempt(
        lambda: re.compile(expression),
        "invalid_tracker",
        f"ids.{what} is not a valid regular expression",
        re.error,
    )


def _expressions(ids: Mapping[str, Any]) -> Result[None]:
    pattern = str(ids["pattern"])
    return bind(
        sequence(
            (
                bind(
                    _compiles(pattern, "pattern"),
                    lambda compiled: require(
                        compiled.groups == 0,
                        "invalid_tracker",
                        "ids.pattern must not capture; write groups as (?:...)",
                    ),
                ),
                bind(
                    _compiles(str(ids["branch_key"]), "branch_key"),
                    lambda compiled: require(
                        "id" in compiled.groupindex,
                        "invalid_tracker",
                        "ids.branch_key needs a named group 'id'",
                    ),
                ),
                *(
                    bind(
                        require(
                            "{id}" in template,
                            "invalid_tracker",
                            "every ids.mention needs {id}",
                        ),
                        lambda _, template=template: bind(
                            _compiles(mention_expression(template, pattern), "mention"),
                            lambda compiled: require(
                                compiled.groups == 1,
                                "invalid_tracker",
                                "an ids.mention may capture only {id}; write other groups as (?:...)",
                            ),
                        ),
                    )
                    for template in ids["mention"]
                ),
            )
        ),
        lambda _: Ok(None),
    )


def mention_expression(template: str, pattern: str) -> str:
    """A mention template with `{id}` replaced by a capturing group for one id."""
    return template.replace("{id}", f"({pattern})")


def _manifest(folder: Path, source: str, document: Mapping[str, Any]) -> Manifest:
    ids, writes = document["ids"], document["writes"]
    return Manifest(
        name=str(document["name"]),
        label=str(document["label"]),
        root=folder,
        source=source,
        kinds=MappingProxyType(
            {WorkItemKind(key): str(value) for key, value in document["kinds"].items()}
        ),
        states=MappingProxyType(
            {LogicalState(key): str(value) for key, value in document["states"].items()}
        ),
        artifacts=tuple(
            Artifact(
                str(item["name"]),
                tuple(map(str, item["children"])),
                str(item.get("estimate", "")),
            )
            for item in document["artifacts"]
        ),
        ids=IdRules(
            str(ids["pattern"]),
            str(ids["branch_key"]),
            tuple(map(str, ids["mention"])),
            bool(ids["mentions_link"]),
        ),
        writes=WriteRules(str(writes["server"]), tuple(map(str, writes["tools"]))),
        tools=MappingProxyType(dict(document.get("tools", {}))),
        connection=MappingProxyType(dict(document["connection"])),
        settings=tuple(str(item["key"]) for item in document["settings"]),
        planning=tuple(
            PlanningReply(str(item["key"]), str(item["description"]))
            for item in document["planning"]["replies"]
        ),
        required_settings=tuple(
            str(item["key"]) for item in document["settings"] if item["required"]
        ),
        text_format=str(document["text_format"]),
        document=MappingProxyType(dict(document)),
    )


# --- all folders ----------------------------------------------------------------------------


def _folders(root: Path) -> tuple[Path, ...]:
    return (
        tuple(sorted(path.parent for path in root.glob(f"*/{MANIFEST}")))
        if root.is_dir()
        else ()
    )


def shipped(root: Path = SHIPPED_ROOT) -> tuple[Result[Manifest], ...]:
    return tuple(read_manifest(folder, "shipped") for folder in _folders(root))


def onboarded(repo: Path) -> tuple[Result[Manifest], ...]:
    """Onboarded folders; one the user has not trusted, or that changed since, is an `Err`."""
    return tuple(
        bind(
            read_manifest(folder, "onboarded"),
            lambda manifest: _trusted(repo, manifest),
        )
        for folder in _folders(repo / ONBOARDED_RELATIVE_PATH)
    )


def _trusted(repo: Path, manifest: Manifest) -> Result[Manifest]:
    return (
        Ok(manifest)
        if trust.is_trusted(repo, manifest.name, manifest.root)
        else err(
            "untrusted_tracker",
            f"onboarded tracker {manifest.name!r} is not trusted as it reads now; "
            f"run `harness tracker show {manifest.name}` and follow it",
        )
    )


def everything(repo: Path, root: Path = SHIPPED_ROOT) -> tuple[Result[Manifest], ...]:
    return (*shipped(root), *onboarded(repo))


def usable(repo: Path, root: Path = SHIPPED_ROOT) -> tuple[Manifest, ...]:
    return oks(everything(repo, root))


def problems(repo: Path, root: Path = SHIPPED_ROOT) -> tuple[Failure, ...]:
    return failures(everything(repo, root))


def find(
    repo: Path, name: str, source: str, root: Path = SHIPPED_ROOT
) -> Result[Manifest]:
    folder = (root if source == "shipped" else repo / ONBOARDED_RELATIVE_PATH) / name
    return bind(
        require(
            (folder / MANIFEST).is_file(),
            "unknown_tracker",
            f"there is no {source} tracker named {name!r}",
        ),
        lambda _: bind(
            read_manifest(folder, source),
            lambda manifest: (
                _trusted(repo, manifest) if source == "onboarded" else Ok(manifest)
            ),
        ),
    )


# --- the repository's tracker ---------------------------------------------------------------


def resolve_among(
    results: tuple[Result[Manifest], ...], repo: Path, settings: Result[Settings]
) -> Resolution:
    """Like `resolve`, choosing among folders already read (see `everything`)."""
    match settings:
        case Err(failure):
            return Invalid(failure)
        case Ok(chosen):
            found = next(
                (
                    manifest
                    for manifest in oks(results)
                    if (manifest.name, manifest.source)
                    == (chosen.tracker.name, chosen.tracker.source)
                ),
                None,
            )
            return (
                _resolution(_with_values(found, chosen.tracker))
                if found is not None
                else resolve(repo, settings)
            )


def resolve(
    repo: Path, settings: Result[Settings], root: Path = SHIPPED_ROOT
) -> Resolution:
    """The tracker the settings select: not configured, active with its values, or invalid."""
    match settings:
        case Err(failure):
            return Invalid(failure)
        case Ok(chosen):
            return _resolution(
                bind(
                    find(repo, chosen.tracker.name, chosen.tracker.source, root),
                    lambda manifest: _with_values(manifest, chosen.tracker),
                )
            )


def _resolution(result: Result[Active]) -> Resolution:
    match result:
        case Ok(active):
            return active
        case Err(failure):
            return Invalid(failure)


def _with_values(manifest: Manifest, selection: Selection) -> Result[Active]:
    missing = tuple(
        key
        for key in manifest.required_settings
        if not selection.values.get(key, "").strip()
    )
    unknown = tuple(key for key in selection.values if key not in manifest.settings)
    return bind(
        sequence(
            (
                require(
                    not missing,
                    "invalid_settings",
                    f"tracker.values is missing {list(missing)} for {manifest.name}",
                ),
                require(
                    not unknown,
                    "invalid_settings",
                    f"tracker.values has {list(unknown)}, which {manifest.name} does not declare",
                ),
            )
        ),
        lambda _: Ok(Active(manifest, selection.values)),
    )


def connection_command(
    manifest: Manifest, values: Mapping[str, str], repo: Path
) -> tuple[str, tuple[str, ...]]:
    """The command and arguments that start the tracker's MCP server, with values filled in."""
    fill = {**values, "plugin_root": str(PLUGIN_ROOT), "repo": str(repo)}
    return (
        str(manifest.connection["command"]),
        tuple(
            str(arg).format_map(_Values(fill))
            for arg in manifest.connection.get("args", ())
        ),
    )


class _Values(
    dict
):  # format_map leaves an unknown placeholder empty instead of raising
    def __missing__(self, key: str) -> str:
        return ""


def selected(
    repo: Path, settings: Result[Settings], root: Path = SHIPPED_ROOT
) -> Result[Active]:
    """The selected tracker as a result: its manifest and values, or why it cannot be used."""
    match resolve(repo, settings, root):
        case Active() as active:
            return Ok(active)
        case Invalid(failure):
            return Err(failure)
        case NotConfigured(reason):
            return err("not_configured", reason)


def open_selected(repo: Path, settings: Result[Settings]) -> Result[TrackerOps]:
    return bind(selected(repo, settings), lambda active: open_tracker(active, repo))


def open_tracker(active: Active, repo: Path) -> Result[TrackerOps]:
    """The active tracker's operations, connected the way its manifest says."""
    return build(active, repo, _transport(active, repo))


def _transport(active: Active, repo: Path) -> Transport:
    from . import transport

    match active.manifest.connection.get("kind"):
        case "mcp":
            command, args = connection_command(active.manifest, active.values, repo)
            return transport.mcp(
                command, args, float(active.manifest.connection.get("timeout", 30))
            )
        case _:
            return transport.unavailable(
                f"{active.manifest.name} is not reached through a provider server"
            )


def build(active: Active, repo: Path, call: Transport) -> Result[TrackerOps]:
    """The tracker's operations, from the `adapter(context)` its folder's adapter.py exports."""
    manifest = active.manifest
    context = AdapterContext(manifest, active.values, repo, call)
    return bind(
        bind(
            require(
                manifest.source == "shipped"
                or trust.is_trusted(repo, manifest.name, manifest.root),
                "untrusted_tracker",
                f"onboarded tracker {manifest.name!r} changed after it was trusted",
            ),
            lambda _: _adapter_function(manifest),
        ),
        lambda adapter: bind(
            attempt(
                lambda: adapter(context),
                "invalid_tracker",
                f"{manifest.name}/{ADAPTER} adapter(context) failed",
                Exception,
            ),
            lambda ops: _built(manifest, ops),
        ),
    )


def _adapter_function(manifest: Manifest) -> Result[Any]:
    module_name = f"harness_tracker_{manifest.source}_{manifest.name.replace('-', '_')}"
    return bind(
        attempt(
            lambda: _import(module_name, manifest.root / ADAPTER),
            "invalid_tracker",
            f"{manifest.name}/{ADAPTER} could not be loaded",
            Exception,
        ),
        lambda module: (
            Ok(module.adapter)
            if callable(getattr(module, "adapter", None))
            else err(
                "invalid_tracker",
                f"{manifest.name}/{ADAPTER} does not export adapter(context)",
            )
        ),
    )


def require_replies(manifest: Manifest, replies: Mapping[str, Any]) -> Result[None]:
    """Every reply the tracker's planning reads is present, or which are missing and how to fetch them."""
    missing = tuple(reply for reply in manifest.planning if reply.key not in replies)
    return require(
        not missing,
        "missing_replies",
        f"{manifest.name} planning needs these replies, fetched through the host's tools and "
        "passed as --replies: "
        + "; ".join(f"{reply.key} ({reply.description})" for reply in missing),
    )


def onboarded_writes(repo: Path) -> tuple[Result[WriteRules], ...]:
    """What each onboarded folder says writes, read on its own: trusted or not, valid or not.

    Counting a broken or untrusted folder's writes can only ask for more approvals, never fewer;
    a folder whose writes cannot be read at all is an `Err`, so the rules can fail closed.
    """
    return tuple(
        _declared_writes(folder) for folder in _folders(repo / ONBOARDED_RELATIVE_PATH)
    )


def _declared_writes(folder: Path) -> Result[WriteRules]:
    return bind(
        attempt(
            lambda: json.loads((folder / MANIFEST).read_text(encoding="utf-8")),
            "invalid_tracker",
            f"{folder.name}/{MANIFEST} could not be read",
            OSError,
            ValueError,
        ),
        lambda document: _write_rules(folder, document),
    )


def _write_rules(folder: Path, document: Any) -> Result[WriteRules]:
    writes = document.get("writes") if isinstance(document, dict) else None
    server = writes.get("server") if isinstance(writes, dict) else None
    tools = writes.get("tools") if isinstance(writes, dict) else None
    return (
        Ok(WriteRules(server, tuple(tools)))
        if isinstance(server, str)
        and isinstance(tools, list)
        and all(isinstance(tool, str) for tool in tools)
        else err(
            "invalid_tracker",
            f"onboarded tracker {folder.name!r} does not say which tools write "
            f"(writes.server, writes.tools in {MANIFEST}); fix or remove the folder",
        )
    )


def _import(module_name: str, file: Path) -> Any:
    """Run the adapter's source as it reads now.

    Compiled here rather than through the import system, so Python neither writes a cache file
    into the tracker folder (which would change its trusted digest) nor runs a cached one that
    could differ from the source the user reviewed.
    """
    module = types.ModuleType(module_name)
    module.__file__ = str(file)
    exec(compile(file.read_bytes(), str(file), "exec"), module.__dict__)
    return module


def _built(manifest: Manifest, ops: Any) -> Result[TrackerOps]:
    return (
        Ok(ops)
        if isinstance(ops, TrackerOps)
        else err(
            "invalid_tracker",
            f"{manifest.name}/{ADAPTER} adapter(context) did not return TrackerOps",
        )
    )
