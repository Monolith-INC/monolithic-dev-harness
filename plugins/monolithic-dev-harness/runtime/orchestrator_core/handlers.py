from __future__ import annotations

from pathlib import Path
from typing import Any

from integrations.planning import as_float

from .artifact_validator import critiques_from_results, validate_artifact
from .ingest import ingest_file, ingest_from_text
from .reflection import (
    ReflectionState,
    append_mistake,
    evaluate_reflection,
    load_mistakes,
)
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
        return {
            "ok": False,
            "error": "file_path is required",
            "instructions": instructions,
        }

    path = Path(file_path)
    if not path.is_file():
        return {
            "ok": False,
            "error": f"file not found: {file_path}",
            "instructions": instructions,
        }

    record = ingest_file(path)
    results = validate_artifact(
        record, hierarchy_parent_is_feature=hierarchy_ok, state_dir=state_dir
    )
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
        record = ingest_from_text(
            draft_override, filename=Path(file_path).stem if file_path else None
        )
    elif file_path:
        record = ingest_file(Path(file_path))
    else:
        return {
            "ok": False,
            "error": "file_path or draft_content required",
            "instructions": instructions,
        }

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

    decision = evaluate_reflection(
        critiques, state=state, max_attempts=max_attempts, has_draft=True
    )

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
    from core.result import Err, Ok
    from harness import settings

    from .capacity import format_plan, plan_iteration
    from .estimation import config_diagnostics, estimate_hours, load_config
    from .project_config import project_root_of

    iteration_ref = str(arguments.get("iteration_ref", "")).strip()
    provider_name = str(arguments.get("provider", "filesystem")).strip() or "filesystem"

    project_root = project_root_of(state_dir)
    replies = arguments.get("replies") or {}
    if not isinstance(replies, dict):
        return {
            "ok": False,
            "error": "replies must be an object",
            "instructions": instructions,
        }
    match _capacity_source(
        provider_name, project_root, settings.load(project_root), replies
    ):
        case Ok(provider):
            pass
        case Err(failure):
            return {"ok": False, "error": failure.message, "instructions": instructions}

    iteration_result = provider.fetch_iteration(iteration_ref)
    if not iteration_result.ok:
        return {
            "ok": False,
            "error": iteration_result.error,
            "instructions": instructions,
        }

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
    from core.result import Err, Ok, bind
    from harness import settings

    from .estimation import (
        TaskInput,
        config_diagnostics,
        estimate_breakdown,
        load_config,
    )
    from .project_config import project_root_of

    if not isinstance(arguments, dict):
        return {
            "ok": False,
            "error": "arguments must be an object",
            "instructions": instructions,
        }

    story_id = _as_text(arguments.get("story_id"))
    if not story_id:
        return {
            "ok": False,
            "error": "story_id is required",
            "instructions": instructions,
        }

    raw_tasks = arguments.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return {
            "ok": False,
            "error": "tasks must be a non-empty list",
            "instructions": instructions,
        }

    replies = arguments.get("replies") or {}
    if not isinstance(replies, dict):
        return {
            "ok": False,
            "error": "replies must be an object",
            "instructions": instructions,
        }

    assignee = _as_text(arguments.get("assignee")) or None

    tasks = [
        TaskInput(
            task_id=_as_text(entry.get("id")) or _as_text(entry.get("task_id")),
            title=_as_text(entry.get("title")),
            current_hours=as_float(entry.get("current_hours")),
            weight=as_float(entry.get("weight")),
        )
        for entry in raw_tasks
        if isinstance(entry, dict)
    ]
    if not tasks:
        return {
            "ok": False,
            "error": "no usable task entries",
            "instructions": instructions,
        }

    # A Task with no id cannot be written, so its share would vanish from the board while
    # still counting toward the total. Refuse rather than silently under-record the Story.
    unidentified = [t.title or "<untitled>" for t in tasks if not t.task_id]
    if unidentified:
        return {
            "ok": False,
            "error": f"every task needs an id; missing on: {', '.join(unidentified)}",
            "instructions": instructions,
        }

    project_root = project_root_of(state_dir)
    tracker = _tracker(project_root, settings.load(project_root))
    iteration_ref = _as_text(arguments.get("iteration_ref")) or None

    # Capacity is checked when asked for: replies were given, or a sprint was named. Once asked, a
    # check that cannot run (no usable tracker, a reply missing) stops the run, since writing
    # hours past an unchecked ceiling is what the check exists to prevent. What the check finds
    # (nobody to match, an unreadable sprint) is reported and the estimate stands.
    asked = bool(replies) or iteration_ref is not None
    match bind(tracker, lambda found: _planning(found, replies)) if asked else Ok(None):
        case Err(failure):
            return {
                "ok": False,
                "error": f"capacity cannot be checked: {failure.message}",
                "instructions": instructions,
            }
        case Ok(None):
            availability, provider_warnings, capacity_errors = None, (), ()
        case Ok(planning):
            availability, provider_warnings, capacity_errors = _assignee_capacity(
                planning, replies, iteration_ref or "current", assignee
            )

    config = load_config(state_dir)
    estimate = estimate_breakdown(
        story_id,
        as_float(arguments.get("story_points")),
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
    # stale hours behind is exactly the drift this feature exists to prevent. The tracker names
    # its own hour fields; a tracker that records no hours, or none usable, gets no writes and a
    # note to record the figures by hand.
    hour_fields = _hour_fields(tracker)
    changed = (
        [] if estimate.blocked else [task for task in estimate.tasks if task.changed]
    )
    write_ops = [
        {"item_id": task.task_id, "fields": dict(fields)}
        for task in changed
        if (fields := hour_fields(task.hours, task.is_new))
    ]
    by_hand = (
        (f"record these hours by hand: {_no_hours(tracker)}",)
        if changed and not write_ops
        else ()
    )

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
            + list(provider_warnings)
            + list(config_diagnostics(config))
            + list(capacity_errors)
            + list(by_hand)
        ),
        "capacity_errors": list(capacity_errors),
        "instructions": instructions,
    }


def _tracker(project_root: Path, loaded: Any) -> Any:
    """The selected tracker's manifest and operations, as a result."""
    from core.result import bind, fmap
    from integrations import registry

    return bind(
        registry.selected(project_root, loaded),
        lambda active: fmap(
            registry.open_tracker(active, project_root),
            lambda tracker: (active.manifest, tracker),
        ),
    )


def _planning(found: Any, replies: dict[str, Any]) -> Any:
    """The tracker's operations, once every reply its planning reads is present."""
    from core.result import fmap
    from integrations import registry

    manifest, tracker = found
    return fmap(registry.require_replies(manifest, replies), lambda _: tracker)


def _assignee_capacity(
    tracker: Any, replies: dict[str, Any], iteration_ref: str, assignee: str | None
) -> tuple[Any, tuple[str, ...], tuple[str, ...]]:
    """(availability, warnings, capacity errors) for the assignee in the sprint."""
    from .capacity import availability_for
    from .providers import TrackerProvider

    provider = TrackerProvider(tracker, replies)
    sprint = provider.fetch_iteration(iteration_ref)
    items = provider.fetch_work_items(iteration_ref) if sprint.ok else sprint
    availability = (
        availability_for(sprint.data, assignee, items=items.data if items.ok else None)
        if sprint.ok
        else None
    )
    found = (
        ()
        if availability is not None
        else (f"iteration unreadable: {sprint.error}",)
        if not sprint.ok
        else ("the sprint records no team capacity, so it was not checked",)
        if not sprint.data.members
        else (f"assignee '{assignee}' not matched to a team member",)
        if assignee
        else ("no assignee on the story, so capacity was not checked",)
    )
    return (
        availability,
        sprint.warnings + (items.warnings if sprint.ok else ()),
        (() if items.ok else (f"iteration items unreadable: {items.error}",)) + found,
    )


def _hour_fields(tracker: Any) -> Any:
    from core.result import Ok

    match tracker:
        case Ok((_, operations)):
            return operations.hour_fields
        case _:
            return lambda hours, first: {}


def _no_hours(tracker: Any) -> str:
    from core.result import Err

    match tracker:
        case Err(failure):
            return failure.message
        case _:
            return "the tracker records no hours"


def _capacity_source(
    provider_name: str,
    project_root: Path,
    loaded: Any,
    replies: dict[str, Any],
) -> Any:
    """The user's planning files, or the selected tracker reading the replies a skill fetched."""
    from core.result import Ok, bind, err, fmap

    from .project_config import from_settings
    from .providers import FilesystemProvider, TrackerProvider

    match provider_name:
        case "filesystem":
            return Ok(
                FilesystemProvider(
                    from_settings(loaded).resolve_artifacts_dir(project_root)
                )
            )
        case "tracker":
            return fmap(
                bind(
                    _tracker(project_root, loaded),
                    lambda found: _planning(found, replies),
                ),
                lambda tracker: TrackerProvider(tracker, replies),
            )
        case _:
            return err(
                "invalid_request",
                f"unknown provider: {provider_name}; use filesystem or tracker",
            )


def _as_text(value: Any) -> str:
    """Coerce a JSON scalar to text. Objects and arrays are not identifiers."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


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
