from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import build_skill_prompt, critiques_to_error_log
from .artifact_validator import critiques_from_results, validate_artifact
from .ingest import ingest_from_text, ingest_file
from .reflection import ReflectionState, append_mistake, evaluate_reflection, load_mistakes
from .report_formatter import format_terminal_report, persist_report


def _load_skill_instructions(skills_dir: Path, skill_name: str) -> str:
    path = skills_dir / skill_name / "SKILL.md"
    if not path.is_file():
        return f"# {skill_name}\n\n(SKILL.md not found)\n"
    return path.read_text(encoding="utf-8")


def handle_validate_artifact(
    arguments: dict[str, Any],
    *,
    skills_dir: Path,
    state_dir: Path,
    instructions: str,
) -> dict[str, Any]:
    file_path = arguments.get("file_path", "").strip()
    persist = bool(arguments.get("persist", False))
    hierarchy_ok = arguments.get("hierarchy_parent_is_feature")
    if hierarchy_ok is not None:
        hierarchy_ok = bool(hierarchy_ok)

    if not file_path:
        return {"ok": False, "error": "file_path is required", "instructions": instructions}

    path = Path(file_path)
    if not path.is_file():
        return {"ok": False, "error": f"file not found: {file_path}", "instructions": instructions}

    record = ingest_file(path)
    results = validate_artifact(record, hierarchy_parent_is_feature=hierarchy_ok, state_dir=state_dir)
    report = format_terminal_report(record, results)
    critiques = critiques_from_results(results)
    outcome = "pass" if not any(r.result == "FAIL" for r in results) else "fail"

    report_path = None
    if persist:
        report_path = str(persist_report(record, report, state_dir=state_dir))

    return {
        "ok": True,
        "outcome": outcome,
        "report": report,
        "critiques": critiques,
        "report_path": report_path,
        "artifact_type": record.type,
        "artifact_title": record.title,
        "instructions": instructions,
    }


def handle_auto_fix_artifact(
    arguments: dict[str, Any],
    *,
    skills_dir: Path,
    state_dir: Path,
    instructions: str,
) -> dict[str, Any]:
    file_path = arguments.get("file_path", "").strip()
    draft_override = arguments.get("draft_content", "").strip()
    attempt = int(arguments.get("attempt", 0))
    max_attempts = int(arguments.get("max_attempts", 3))
    record_mistake = bool(arguments.get("record_mistake", True))

    state = ReflectionState(attempt=attempt)
    if state.last_critiques and attempt:
        state = ReflectionState(
            attempt=attempt,
            last_critiques=tuple(arguments.get("last_critiques", [])),
        )

    if not file_path and not draft_override:
        mistakes = load_mistakes(state_dir, skill_name="auto-fix-artifact")
        return {
            "ok": True,
            "mode": "instructions",
            "mistakes": mistakes[-10:],
            "instructions": instructions,
        }

    if draft_override:
        record = ingest_from_text(draft_override, filename=Path(file_path).stem if file_path else None)
    elif file_path:
        record = ingest_file(Path(file_path))
    else:
        return {"ok": False, "error": "file_path or draft_content required", "instructions": instructions}

    results = validate_artifact(record, state_dir=state_dir)
    critiques = critiques_from_results(results)
    report = format_terminal_report(record, results)

    if not critiques:
        return {
            "ok": True,
            "mode": "completed",
            "blocked": False,
            "outcome": "pass",
            "report": report,
            "critiques": [],
            "reflection": state.to_dict(),
            "instructions": instructions,
        }

    decision = evaluate_reflection(critiques, state=state, max_attempts=max_attempts, has_draft=True)

    if decision.blocked and record_mistake and critiques:
        append_mistake(
            state_dir,
            flaw="; ".join(critiques)[:500],
            skill_name="auto-fix-artifact",
            artifact=file_path or "inline-draft",
        )

    return {
        "ok": True,
        "mode": decision.mode,
        "blocked": decision.blocked,
        "outcome": "pass" if not critiques else "fail",
        "report": report,
        "critiques": decision.critiques,
        "reflection": decision.reflection.to_dict(),
        "instructions": instructions,
    }


def handle_plan_capacity(
    arguments: dict[str, Any],
    *,
    skills_dir: Path,
    state_dir: Path,
    instructions: str,
) -> dict[str, Any]:
    """Compare a sprint's available hours against what it has taken on.

    Reads only. Any hour figure it suggests is returned as a planned write for a human to
    confirm -- this handler never sends anything to a backlog system.
    """
    from .capacity import format_plan, plan_iteration
    from .estimation import config_diagnostics, estimate_hours, load_config
    from .project_config import load_project_config
    from .providers import get_provider

    iteration_ref = str(arguments.get("iteration_ref", "")).strip()
    provider_name = str(arguments.get("provider", "filesystem")).strip() or "filesystem"

    # state_dir is `<project>/.agile-backlog-toolkit`, so its parent is the project root.
    project_root = state_dir.parent
    project_config = load_project_config(project_root)

    provider_kwargs: dict[str, Any] = {}
    if provider_name == "azure-devops":
        payloads = arguments.get("payloads") or {}
        if not isinstance(payloads, dict):
            return {"ok": False, "error": "payloads must be an object", "instructions": instructions}
        provider_kwargs["payloads"] = payloads
        provider_kwargs["process"] = arguments.get("process") or project_config.azure.process

        # Identity is only needed when the provider has to fetch for itself. With payloads
        # injected, the caller has already done the reading and none of this applies.
        if not provider_kwargs["payloads"]:
            missing = project_config.missing()
            if missing:
                return {
                    "ok": False,
                    "error": (
                        f"Azure configuration incomplete: {', '.join(missing)} not set. "
                        "Discover the values through the Azure DevOps MCP tools, then persist "
                        "them with: bin/agile-backlog-toolkit config --set azure.<key>=<value>"
                    ),
                    "missing_config": missing,
                    "instructions": instructions,
                }

    provider = get_provider(
        provider_name,
        artifacts_dir=project_config.resolve_artifacts_dir(project_root),
        **provider_kwargs,
    )
    if provider is None:
        return {"ok": False, "error": f"unknown provider: {provider_name}", "instructions": instructions}

    iteration_result = provider.fetch_iteration(iteration_ref)
    if not iteration_result.ok:
        return {"ok": False, "error": iteration_result.error, "instructions": instructions}

    items_result = provider.fetch_work_items(iteration_ref)
    if not items_result.ok:
        return {"ok": False, "error": items_result.error, "instructions": instructions}

    items = items_result.data or []
    plan = plan_iteration(iteration_result.data, items)

    config = load_config(state_dir)
    suggestions = []
    for item in items:
        if item.has_estimate or item.points is None:
            continue
        estimate = estimate_hours(item.points, config=config)
        if estimate is None:
            continue
        suggestions.append(
            {
                "item_id": item.item_id,
                "title": item.title,
                "points": item.points,
                "suggested_hours": estimate.hours,
                "provenance": estimate.provenance,
                "confidence": estimate.confidence,
                "describe": estimate.describe(),
                "requires_confirmation": True,
            }
        )

    return {
        "ok": True,
        "iteration_ref": iteration_ref,
        "provider": provider_name,
        "report": format_plan(plan),
        "available_hours": plan.available_hours,
        "planned_hours": plan.planned_hours,
        "utilisation": plan.utilisation,
        "overcommitted": plan.overcommitted,
        "items_total": plan.items_total,
        "items_estimated": plan.items_estimated,
        "warnings": (
            list(plan.warnings)
            + list(iteration_result.warnings)
            + list(items_result.warnings)
            + list(config_diagnostics(config))
        ),
        "suggestions": suggestions,
        "instructions": instructions,
    }


def handle_estimate_breakdown(
    arguments: dict[str, Any],
    *,
    skills_dir: Path,
    state_dir: Path,
    instructions: str,
) -> dict[str, Any]:
    """Derive hours for every Task under a Story and check them against the assignee.

    Deterministic: the split, the capacity arithmetic and the block decision are computed
    here rather than reasoned about, so the same inputs always produce the same hours.

    Returns the write operations to apply — it performs none itself. When `blocked` is set,
    `write_ops` is empty: work that cannot fit is never written.
    """
    from .capacity import availability_for
    from .estimation import TaskInput, config_diagnostics, estimate_breakdown, load_config
    from .project_config import load_project_config
    from .providers.azure_devops import AzureDevOpsProvider
    from .providers.azure_devops import fields as azure_fields

    if not isinstance(arguments, dict):
        return {"ok": False, "error": "arguments must be an object", "instructions": instructions}

    story_id = _as_text(arguments.get("story_id"))
    if not story_id:
        return {"ok": False, "error": "story_id is required", "instructions": instructions}

    raw_tasks = arguments.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return {"ok": False, "error": "tasks must be a non-empty list", "instructions": instructions}

    payloads = arguments.get("payloads") or {}
    if not isinstance(payloads, dict):
        return {"ok": False, "error": "payloads must be an object", "instructions": instructions}

    assignee = _as_text(arguments.get("assignee")) or None

    tasks = [
        TaskInput(
            task_id=_as_text(entry.get("id")) or _as_text(entry.get("task_id")),
            title=_as_text(entry.get("title")),
            current_hours=_as_float(entry.get("current_hours")),
            weight=_as_float(entry.get("weight")),
        )
        for entry in raw_tasks
        if isinstance(entry, dict)
    ]
    if not tasks:
        return {"ok": False, "error": "no usable task entries", "instructions": instructions}

    # A Task with no id cannot be written, so its share would vanish from the board while
    # still counting toward the total. Refuse rather than silently under-record the Story.
    unidentified = [t.title or "<untitled>" for t in tasks if not t.task_id]
    if unidentified:
        return {
            "ok": False,
            "error": f"every task needs an id; missing on: {', '.join(unidentified)}",
            "instructions": instructions,
        }

    project_root = state_dir.parent
    project_config = load_project_config(project_root)
    process = _as_text(arguments.get("process")) or project_config.azure.process

    # Capacity is optional: without it the estimate still stands, it is simply unchecked.
    # But a failure to read it is not the same as not asking, so it is reported.
    availability = None
    capacity_errors: list[str] = []
    provider_warnings: list[str] = []
    iteration_ref = _as_text(arguments.get("iteration_ref")) or None
    if payloads:
        provider = AzureDevOpsProvider(payloads=payloads, process=process)
        iteration_result = provider.fetch_iteration(iteration_ref or "current")
        provider_warnings.extend(iteration_result.warnings)
        if not iteration_result.ok:
            capacity_errors.append(f"iteration unreadable: {iteration_result.error}")
        else:
            items_result = provider.fetch_work_items(iteration_ref or "current")
            provider_warnings.extend(items_result.warnings)
            if not items_result.ok:
                capacity_errors.append(f"iteration items unreadable: {items_result.error}")
            availability = availability_for(
                iteration_result.data,
                assignee,
                items=items_result.data if items_result.ok else None,
            )
            if availability is None and assignee:
                capacity_errors.append(f"assignee '{assignee}' not matched to a team member")
            elif availability is None:
                capacity_errors.append("no assignee on the story, so capacity was not checked")

    config = load_config(state_dir)
    estimate = estimate_breakdown(
        story_id,
        _as_float(arguments.get("story_points")),
        tasks,
        config=config,
        assignee=assignee,
        iteration_ref=iteration_ref,
        availability=availability,
    )
    if estimate is None:
        return {
            "ok": True,
            "estimated": False,
            "reason": "no story points, or no tasks — an unestimated item is an honest state",
            "instructions": instructions,
        }

    # Every task whose figure moved is written, including one that dropped to zero: leaving
    # stale Remaining Work behind is exactly the drift this feature exists to prevent.
    write_ops: list[dict[str, Any]] = []
    if not estimate.blocked:
        for task in estimate.tasks:
            if not task.changed:
                continue
            ops = {azure_fields.field_ref(azure_fields.REMAINING_WORK): task.hours}
            if azure_fields.supports_original_estimate(process) and task.is_new and task.hours > 0:
                ops[azure_fields.field_ref(azure_fields.ORIGINAL_ESTIMATE)] = task.hours
            write_ops.append({"item_id": task.task_id, "fields": ops})

    return {
        "ok": True,
        "estimated": True,
        "story_id": story_id,
        "report": estimate.describe(),
        "blocked": estimate.blocked,
        "overflow_hours": estimate.overflow_hours,
        "resolution_options": list(estimate.resolution_options()),
        "total_hours": estimate.total_hours,
        "provenance": estimate.provenance,
        "capacity_known": estimate.capacity_known,
        "remaining_hours": estimate.remaining_hours,
        "tasks": [
            {
                "item_id": t.task_id,
                "title": t.title,
                "role": t.role,
                "hours": t.hours,
                "previous_hours": t.previous_hours,
                "changed": t.changed,
            }
            for t in estimate.tasks
        ],
        "changes": [t.describe_change() for t in estimate.changes],
        "write_ops": write_ops,
        "warnings": (
            list(estimate.warnings)
            + provider_warnings
            + list(config_diagnostics(config))
            + capacity_errors
        ),
        "capacity_errors": capacity_errors,
        "instructions": instructions,
    }


def _as_text(value: Any) -> str:
    """Coerce a JSON scalar to text. Objects and arrays are not identifiers."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


HANDLERS = {
    "validate-artifact": handle_validate_artifact,
    "auto-fix-artifact": handle_auto_fix_artifact,
    "plan-capacity": handle_plan_capacity,
    "estimate-breakdown": handle_estimate_breakdown,
}


def execute_handler(
    skill_name: str,
    arguments: dict[str, Any],
    *,
    skills_dir: Path,
    state_dir: Path,
) -> dict[str, Any]:
    instructions = _load_skill_instructions(skills_dir, skill_name)
    handler = HANDLERS.get(skill_name)
    if handler is None:
        return {"ok": True, "mode": "instructions", "instructions": instructions}
    return handler(
        arguments,
        skills_dir=skills_dir,
        state_dir=state_dir,
        instructions=instructions,
    )
