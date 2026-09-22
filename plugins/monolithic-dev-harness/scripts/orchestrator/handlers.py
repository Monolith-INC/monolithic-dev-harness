from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from artifact_profiles.resolution import resolution_profile
from artifact_profiles.spec import spec_profile
from artifact_reflection import ArtifactContext, ReflectionEngine, ReflectionState
from resolution_runtime import load_resolution_template, plan_resolution
from resolve_ticket_hook import on_resolve_ticket
from spec_runtime import load_template, plan_spec_generation, slug_ticket_id
from spec_start_hook import on_start_ticket

from .invocation import HandlerResult, Invocation


def _skills_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "skills"


def _source(arguments: Any) -> str:
    for key in ("source_text", "description", "work_item_description", "requirements"):
        value = arguments.get(key, "")
        if value:
            return str(value)
    return ""


def _reflection(
    arguments: Any,
    invocation: Invocation,
    *,
    skill: str,
    kind: str,
    ticket_id: str,
    draft: str,
    ground_truth: dict[str, Any],
) -> tuple[ReflectionState, Any]:
    state = ReflectionState(attempt=invocation.attempt)
    history = arguments.get("critic_history", arguments.get("reflection_history", []))
    if not isinstance(history, list):
        history = []
    context = ArtifactContext(
        skill,
        kind,
        ticket_id,
        slug_ticket_id(ticket_id),
        draft,
        ground_truth,
        int(arguments.get("max_attempts", 3)),
    )
    decision = ReflectionEngine(
        spec_profile(kind) if skill == "write-spec" else resolution_profile()
    ).run_with_mistakes(context, state=state, mistakes=history)
    return decision.reflection, decision


def handle_write_spec(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    ticket_id = str(arguments["ticket_id"])
    spec_kind = str(arguments.get("spec_kind", "tech-spec"))
    plan = plan_spec_generation(
        ticket_id,
        source_text=_source(arguments),
        existing_artifacts=arguments.get("existing_artifacts", []),
        kind=spec_kind,
    )
    try:
        template = load_template(_skills_dir(), spec_kind)
    except FileNotFoundError:
        template = (
            f"# {spec_kind}\n\n<!-- Supply the provider artifact content here. -->\n"
        )
    draft = str(arguments.get("draft_content", "")).strip()
    reflection, decision = _reflection(
        arguments,
        invocation,
        skill="write-spec",
        kind=spec_kind,
        ticket_id=ticket_id,
        draft=draft,
        ground_truth=plan.source_hints,
    )
    return HandlerResult(
        product={
            "ticket_id": ticket_id,
            "spec_kind": spec_kind,
            "artifact_scope": "tracker",
            "required_kinds": list(plan.required_kinds),
            "missing_kinds": list(plan.missing_kinds),
            "template": template,
            "source_hints": plan.source_hints,
            "critiques": "; ".join(decision.critiques),
            "mode": decision.mode if draft else "instructions",
            "instructions": instructions,
        },
        reflection=reflection.to_dict(),
    )


def handle_start_ticket(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    ticket_id = str(arguments.get("ticket_id", "")).strip()
    draft_location = str(arguments.get("draft_location", "")).strip()
    title = str(arguments.get("title", "")).strip()
    draft_required = not ticket_id and not (
        draft_location or title or _source(arguments).strip()
    )
    next_actions = [
        "Call workflow_tracking_status and stop if tracking is paused.",
    ]
    if not ticket_id:
        next_actions.extend(
            [
                "Ask for a draft location; if none exists, interview the user "
                "for title, kind, requirements, acceptance criteria, "
                "constraints, and parent work item.",
                "Create the tracker item with tracker_create_work_item from "
                "the accepted draft.",
                "Create and check out a work-item branch from the "
                "bootstrap-selected template, substituting the created ticket "
                "key and a concise slug.",
                "Transition the created work item to logical in_progress.",
                "Generate and publish the required specification artifacts "
                "before implementation writes.",
            ]
        )
    else:
        next_actions.extend(
            [
                "Fetch the existing tracker item and artifacts.",
                "Create or switch to a work-item branch from the "
                "bootstrap-selected template when the current branch does not "
                "map to this ticket.",
                "Transition the work item to logical in_progress.",
                "Generate and publish any missing specification artifacts "
                "before implementation writes.",
            ]
        )
    plan = plan_spec_generation(
        ticket_id or title or "new-ticket",
        source_text=_source(arguments),
        existing_artifacts=arguments.get("existing_artifacts", []),
    )
    directive = None if not ticket_id else on_start_ticket(plan)
    if not ticket_id:
        mode = "bootstrap"
    elif directive:
        mode = "instructions"
    else:
        mode = "completed"
    return HandlerResult(
        product={
            "ticket_id": ticket_id,
            "artifact_scope": "tracker",
            "transition_required": "in_progress",
            "ticket_bootstrap_required": not bool(ticket_id),
            "draft_required": draft_required,
            "draft_location": draft_location,
            "spec_plan": plan.to_dict(),
            "write_spec_directive": directive,
            "generation_required": plan.generation_required,
            "next_actions": next_actions,
            "mode": mode,
            "instructions": instructions,
        }
    )


def handle_resolve_ticket(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    ticket_id = str(arguments["ticket_id"])
    artifacts = arguments.get("artifacts", arguments.get("existing_artifacts", []))
    plan = plan_resolution(
        ticket_id,
        source_text=_source(arguments),
        artifacts=artifacts,
        resolution_exists=bool(arguments.get("resolution_exists", False)),
    )
    directive = on_resolve_ticket(plan)
    try:
        template = load_resolution_template(_skills_dir())
    except FileNotFoundError:
        template = "# Resolution Report\n\n<!-- Supply the provider artifact content here. -->\n"
    ground_truth = plan.ground_truth()
    if arguments.get("implementation_summary"):
        ground_truth["implementation_summary"] = str(
            arguments["implementation_summary"]
        )
    draft = str(arguments.get("draft_content", "")).strip()
    reflection, decision = _reflection(
        arguments,
        invocation,
        skill="resolve-ticket",
        kind="resolution-report",
        ticket_id=ticket_id,
        draft=draft,
        ground_truth=ground_truth,
    )
    return HandlerResult(
        product={
            "ticket_id": ticket_id,
            "artifact_scope": "tracker",
            "artifact_kind": "resolution_report",
            "spec_artifacts": list(plan.spec_artifacts),
            "template": template,
            "ground_truth": ground_truth,
            "resolve_directive": directive,
            "resolution_required": plan.resolution_required,
            "critiques": "; ".join(decision.critiques),
            "mode": decision.mode if draft else "instructions",
            "instructions": instructions,
        },
        reflection=reflection.to_dict(),
    )


def handle_review_pr(invocation: Invocation) -> HandlerResult:
    return HandlerResult(
        product={
            "pr_number": invocation.arguments["pr_number"],
            "mode": "instructions",
            "instructions": invocation.instructions,
        }
    )


def _feature_plan(arguments: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    feature_ref = str(
        arguments.get("feature_ref")
        or arguments.get("ticket_id")
        or arguments.get("ref")
        or ""
    )
    raw_children = arguments.get("children")
    children = raw_children if isinstance(raw_children, list) else []
    summarized = []
    for child in children:
        if not isinstance(child, dict):
            continue
        summarized.append(
            {
                "key": child.get("key") or child.get("id"),
                "title": child.get("title"),
                "state": child.get("state"),
                "missing_artifacts": child.get("missing_artifacts") or [],
            }
        )
    return {
        "feature_ref": feature_ref,
        "mode": mode,
        "stories": summarized,
        "ordered_story_keys": [item["key"] for item in summarized if item.get("key")],
        "pr_base": "feature-branch",
        "required_artifact_kinds": [
            "implementation-plan",
            "verification",
            "pull_request",
        ],
    }


def handle_feature_implementation(invocation: Invocation) -> HandlerResult:
    plan = _feature_plan(invocation.arguments, mode="start")
    return HandlerResult(
        product={
            "mode": "instructions",
            "skill": "feature-implementation",
            "plan": plan,
            "instructions": invocation.instructions,
        }
    )


def handle_finish_feature_development(invocation: Invocation) -> HandlerResult:
    plan = _feature_plan(invocation.arguments, mode="finish")
    return HandlerResult(
        product={
            "mode": "instructions",
            "skill": "finish-feature-development",
            "plan": plan,
            "instructions": invocation.instructions,
        }
    )


def handle_reconcile_feature_stack(invocation: Invocation) -> HandlerResult:
    plan = _feature_plan(invocation.arguments, mode="reconcile")
    return HandlerResult(
        product={
            "mode": "instructions",
            "skill": "reconcile-feature-stack",
            "plan": plan,
            "instructions": invocation.instructions,
        }
    )


def handle_merge_story_stack_into_feature(invocation: Invocation) -> HandlerResult:
    plan = _feature_plan(invocation.arguments, mode="merge-story-stack")
    return HandlerResult(
        product={
            "mode": "instructions",
            "skill": "merge-story-stack-into-feature",
            "plan": plan,
            "instructions": invocation.instructions,
        }
    )


def handle_instruction_only(invocation: Invocation) -> HandlerResult:
    return HandlerResult(
        product={
            "mode": "instructions",
            "skill": invocation.manifest.get("name", ""),
            "inputs": invocation.arguments,
            "instructions": invocation.instructions,
        }
    )


_HANDLERS: dict[str, Callable[[Invocation], HandlerResult]] = {
    "start-ticket": handle_start_ticket,
    "write-spec": handle_write_spec,
    "resolve-ticket": handle_resolve_ticket,
    "review-pr": handle_review_pr,
    "feature-implementation": handle_feature_implementation,
    "finish-feature-development": handle_finish_feature_development,
    "reconcile-feature-stack": handle_reconcile_feature_stack,
    "merge-story-stack-into-feature": handle_merge_story_stack_into_feature,
}


def get_handler(skill_name: str) -> Callable[[Invocation], HandlerResult]:
    return _HANDLERS.get(skill_name, handle_instruction_only)
