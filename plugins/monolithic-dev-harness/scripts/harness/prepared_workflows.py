"""Resolve a versioned workflow stage into its project-specific agent handoff.

`routes` and `prepare_stage` return `Result` values; the helpers below raise `_Invalid`, which
only those two edges catch.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from core.result import Result, attempt
from integrations.gateway import TOOLS_BY_NAME

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONTEXT_FILE_LIMIT = 32_000
PROJECT_CONTEXT_TOTAL_LIMIT = 96_000
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
LOCAL_OPERATIONS = {
    "harness.bootstrap.inspect": "Inspect project settings, saved progress, and repository state.",
    "harness.work-session.route": "Match the exact request to saved project work or present a new-session choice.",
    "harness.work-session.start": "Start a separate project work session for the selected request.",
    "harness.work-session.resume": "Resume a paused project work session.",
    "harness.work-session.pause": "Pause project work while preserving its saved context.",
    "harness.work-session.stop": "Stop a project work session without deleting its history.",
    "harness.work-session.select": "Bind this host conversation to one project work session.",
    "harness.doctor": "Check local harness setup and required tools.",
    "harness.workflow.status": "Read the current saved workflow checkpoint.",
    "harness.workflow.checkpoint": "Save a workflow checkpoint without granting write approval.",
    "harness.knowledge.catalog": "List the bounded project knowledge routing catalog.",
    "harness.knowledge.find": "Search the selected harness knowledge store.",
    "harness.knowledge.fetch": "Read a selected harness knowledge item.",
    "harness.suspension.status": "Read whether the user suspended the harness checks; only their own `harness suspend` message does.",
}


class _Invalid(ValueError):
    """A catalog, reference, or request the prepared step cannot be built from."""


def catalog_path(plugin_root: Path = PLUGIN_ROOT) -> Path:
    return plugin_root / "config" / "prepared-workflows.json"


def load_catalog(plugin_root: Path = PLUGIN_ROOT) -> dict[str, Any]:
    path = catalog_path(plugin_root)
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _Invalid(f"cannot read prepared workflow catalog: {exc}") from exc
    if not isinstance(catalog, dict) or catalog.get("version") != 1:
        raise _Invalid("prepared workflow catalog has an unsupported version")
    return catalog


def routes(plugin_root: Path = PLUGIN_ROOT) -> Result[dict[str, tuple[str, ...]]]:
    return attempt(
        lambda: _routes(plugin_root),
        "prepared_workflow_invalid",
        "prepared workflow",
        _Invalid,
    )


def _routes(plugin_root: Path) -> dict[str, tuple[str, ...]]:
    catalog = load_catalog(plugin_root)
    raw_routes = catalog.get("routes")
    stages = catalog.get("stages")
    if not isinstance(raw_routes, dict) or not isinstance(stages, dict):
        raise _Invalid("prepared workflow catalog is missing routes or stages")
    checked: dict[str, tuple[str, ...]] = {}
    for route_id, stage_ids in raw_routes.items():
        if (
            not isinstance(route_id, str)
            or not isinstance(stage_ids, list)
            or not stage_ids
            or not all(
                isinstance(stage_id, str) and stage_id in stages
                for stage_id in stage_ids
            )
        ):
            raise _Invalid(f"route {route_id!r} refers to an unknown stage")
        checked[route_id] = tuple(stage_ids)
    return checked


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _skill_description(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    end = next(
        (i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), len(lines)
    )
    header = lines[1:end]
    index = next(
        (i for i, line in enumerate(header) if line.startswith("description:")), -1
    )
    if index < 0:
        return ""
    value = header[index].partition(":")[2].strip()
    if value in {">", "|", ">-", "|-", ">+", "|+"}:
        block = []
        for line in header[index + 1 :]:
            if line and not line[0].isspace():
                break
            block.append(line.strip())
        return " ".join(part for part in block if part)
    return value.strip("\"'")


def _inside(plugin_root: Path, relative: str, what: str) -> Path:
    """A file inside the harness package, or `_Invalid` naming what was asked for."""
    candidate = (plugin_root / relative).resolve()
    if not candidate.is_relative_to(plugin_root.resolve()):
        raise _Invalid(f"{what} escapes the harness package: {relative}")
    if not candidate.is_file():
        raise _Invalid(f"{what} is missing: {relative}")
    return candidate


def _project_documents(repo: Path) -> tuple[dict[str, str], ...]:
    guidance = repo / "AGENTS.md"
    readme = repo / "README.md"
    ordered = tuple(path for path in (guidance, readme) if path.is_file())
    discovered = tuple(
        target
        for source in ordered
        for href in MARKDOWN_LINK.findall(source.read_text(encoding="utf-8"))
        if (target := _markdown_target(repo, source, href)) is not None
    )
    paths = tuple(dict.fromkeys((*ordered, *discovered)))
    entries: list[dict[str, str]] = []
    total_bytes = 0
    for path in paths:
        resolved = path.resolve()
        try:
            resolved.relative_to(repo.resolve())
        except ValueError:
            continue
        raw = resolved.read_bytes()
        total_bytes += len(raw)
        if len(raw) > PROJECT_CONTEXT_FILE_LIMIT:
            raise _Invalid(f"project context file is too large to preload: {resolved}")
        if total_bytes > PROJECT_CONTEXT_TOTAL_LIMIT:
            raise _Invalid("project context exceeds the prepared handoff size limit")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _Invalid(f"project context is not UTF-8 text: {resolved}") from exc
        entries.append(
            {
                "kind": "project-guidance"
                if resolved.name == "AGENTS.md"
                else "project-document",
                "path": str(resolved),
                "digest": hashlib.sha256(raw).hexdigest(),
                "content": content,
            }
        )
    return tuple(entries)


def _markdown_target(repo: Path, source: Path, href: str) -> Path | None:
    value = href.strip().split(maxsplit=1)[0].strip("<>")
    if not value or value.startswith(("#", "/")) or "://" in value:
        return None
    target = (source.parent / value.split("#", 1)[0]).resolve()
    try:
        target.relative_to(repo.resolve())
    except ValueError:
        return None
    if target.is_dir():
        target = target / "README.md"
    return (
        target
        if target.is_file() and target.suffix.lower() in {".md", ".markdown"}
        else None
    )


def prepare_stage(
    repo: Path,
    route_id: str,
    stage_id: str,
    *,
    plugin_root: Path = PLUGIN_ROOT,
    original_request: str = "",
    available_operations: Iterable[str] | None = None,
) -> Result[dict[str, Any]]:
    """A read-only step package with verified references and skill guidance.

    The step is `ready` only when its inputs are present and the host confirmed, through
    `available_operations`, every tracker or SCM operation it needs.
    """
    return attempt(
        lambda: _prepare_stage(
            repo,
            route_id,
            stage_id,
            plugin_root,
            original_request,
            available_operations,
        ),
        "prepared_workflow_invalid",
        "prepared workflow",
        _Invalid,
    )


def _prepare_stage(
    repo: Path,
    route_id: str,
    stage_id: str,
    plugin_root: Path,
    original_request: str,
    available_operations: Iterable[str] | None,
) -> dict[str, Any]:
    canonical_repo = repo.resolve()
    if not canonical_repo.is_dir():
        raise _Invalid(f"project directory does not exist: {canonical_repo}")
    catalog = load_catalog(plugin_root)
    route_stages = _routes(plugin_root).get(route_id)
    if route_stages is None:
        raise _Invalid(f"unknown prepared route: {route_id}")
    if stage_id not in route_stages:
        raise _Invalid(f"stage {stage_id!r} is not part of route {route_id!r}")
    stage = catalog["stages"].get(stage_id)
    if not isinstance(stage, dict):
        raise _Invalid(f"prepared stage is missing: {stage_id}")

    knowledge = tuple(
        _inside(plugin_root, item, "required harness knowledge")
        for item in stage.get("knowledge", ())
    )
    skill_entries: list[dict[str, str]] = []
    for recommendation in stage.get("skills", ()):
        name = recommendation.get("name", "")
        when = recommendation.get("when", "")
        skill_file = _inside(
            plugin_root, f"skills/{name}/SKILL.md", "recommended skill"
        )
        skill_entries.append(
            {
                "name": name,
                "description": _skill_description(skill_file),
                "when_to_use": when,
                "instructions": str(skill_file),
                "digest": _digest(skill_file),
            }
        )

    operations: list[dict[str, str]] = []
    for operation_id in stage.get("operations", ()):
        if operation_id in LOCAL_OPERATIONS:
            operations.append(
                {
                    "name": operation_id,
                    "kind": "harness-command",
                    "purpose": LOCAL_OPERATIONS[operation_id],
                }
            )
        elif operation_id in TOOLS_BY_NAME:
            tool = TOOLS_BY_NAME[operation_id]
            operations.append(
                {
                    "name": operation_id,
                    "kind": "tracker-or-host-adapter",
                    "purpose": str(tool["description"]),
                }
            )
        else:
            raise _Invalid(
                f"prepared stage {stage_id!r} names an unknown operation: {operation_id}"
            )

    missing_inputs = [
        name
        for name in stage.get("required_inputs", ())
        if name == "original_request" and not original_request.strip()
    ]
    available = (
        None if available_operations is None else frozenset(available_operations)
    )
    missing_host_operations = (
        [
            operation["name"]
            for operation in operations
            if operation["kind"] == "tracker-or-host-adapter"
            and operation["name"] not in available
        ]
        if available_operations is not None
        else []
    )
    host_tools_checked = available is not None

    project_knowledge = _project_documents(canonical_repo)
    package = {
        "catalog_version": catalog["version"],
        "route": {"id": route_id, "stages": list(route_stages)},
        "step": {"id": stage_id, "title": stage["title"]},
        "project_root": str(canonical_repo),
        "original_request": original_request,
        "missing_inputs": missing_inputs,
        "project_knowledge": list(project_knowledge),
        "harness_knowledge": [
            {
                "path": str(path),
                "digest": _digest(path),
                "content": path.read_text(encoding="utf-8"),
            }
            for path in knowledge
        ],
        "operations": operations,
        "recommended_skills": skill_entries,
        "expected_outputs": list(stage.get("outputs", ())),
        "checks": list(stage.get("checks", ())),
        "recovery": list(stage.get("recovery", ())),
        "missing_host_operations": missing_host_operations,
        "host_tools_checked": host_tools_checked,
        "ready": not missing_inputs
        and not missing_host_operations
        and host_tools_checked,
        "host_tool_check": "available operations were confirmed by the active host"
        if host_tools_checked and not missing_host_operations
        else "required operations are declared; the active host must confirm availability",
    }
    package["digest"] = hashlib.sha256(
        json.dumps(package, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return package
