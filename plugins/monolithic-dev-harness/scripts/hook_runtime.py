from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from host_adapters import (
    format_claude_decision,
    format_cursor_decision,
    parse_claude_payload,
    parse_cursor_payload,
)
from integrations.adapters import tracker_adapter
from integrations.config import load_config
from integrations.contracts import IntegrationError
from policy import CanonicalToolEvent, PolicyDecision
from harness.config import PolicyError, load_policy
from policy.commands import git_commands, is_code, writes_code
from policy.git_branch_guard import evaluate_git_branch_guard

LOG_FILE = "/tmp/codex_hook_debug.log"
_WRITE_TOOLS = frozenset(
    {
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "Write",
        "StrReplace",
        "Edit",
        "Delete",
        "delete_file",
        "delete",
        "apply_patch",
    }
)
_MUTATING_GIT = frozenset(
    {
        "commit",
        "push",
        "merge",
        "rebase",
        "pull",
        "cherry-pick",
        "revert",
        "reset",
        "stash",
        "tag",
    }
)

AdapterFormatter = Callable[[PolicyDecision], dict[str, Any]]


def log_debug(message: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")
    except OSError:
        pass


def get_project_root() -> str:
    for key in ("CURSOR_PROJECT_DIR", "CODEX_PROJECT_ROOT", "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(key, "").strip()
        if value and os.path.isdir(value):
            return value
    cwd = os.getcwd()
    while cwd != os.path.dirname(cwd):
        if os.path.exists(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)
    return os.getcwd()


def current_branch(project_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", project_root, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def select_adapter(client: str) -> tuple[Callable[..., Any], AdapterFormatter]:
    if client.strip().lower() == "cursor":
        return parse_cursor_payload, format_cursor_decision
    return parse_claude_payload, format_claude_decision


def emit_decision(client: str, decision: PolicyDecision) -> None:
    if not decision.is_denied() and client.strip().lower() != "cursor":
        return
    _, formatter = select_adapter(client)
    print(json.dumps(formatter(decision)))


def run(client: str, input_data: dict[str, Any]) -> int:
    project_root = get_project_root()
    parser, _ = select_adapter(client)
    event = parser(input_data, project_root=project_root)
    event = CanonicalToolEvent(
        **{**event.__dict__, "branch": current_branch(project_root)}
    )
    decision = evaluate_event(event, input_data)
    if decision.is_denied():
        log_debug(f"DENIED: {decision.reason}")
    emit_decision(client, decision)
    return 0


def evaluate_event(
    event: CanonicalToolEvent, payload: dict[str, Any] | None = None
) -> PolicyDecision:
    command = event.command or ""
    if event.tool_name in {"run_command", "run_shell_command", "Shell", "Bash"}:
        branch_decision = evaluate_git_branch_guard(command, event.workspace_root)
        if branch_decision.is_denied():
            return branch_decision
        checkout_decision = _validate_checkout_convention(command, event.workspace_root)
        if checkout_decision.is_denied():
            return checkout_decision
        if _is_mutating_git(command) or writes_code(
            command, event.workspace_root, _code_patterns(event.workspace_root)
        ):
            return _evaluate_work_context(event)
        return PolicyDecision.allow()

    normalized = _normalized_tool_name(event.tool_name)
    if normalized == "tracker_transition_work_item":
        arguments = _arguments(payload or {})
        if arguments.get("state") == "done":
            return _evaluate_completion(event)
        return PolicyDecision.allow()

    if event.tool_name in _WRITE_TOOLS and _edits_code(event):
        return _evaluate_work_context(event)
    return PolicyDecision.allow()


def _code_patterns(project_root: str) -> list[str] | None:
    """The policy's source and test globs: the files "spec before code" covers.

    `None` (every file but git's and the harness's) when the policy names none or cannot be read.
    """
    try:
        policy = load_policy(Path(project_root))
    except (PolicyError, OSError):
        return None
    patterns = [
        pattern
        for group in policy.get("tests_required", [])
        for key in ("source", "tests")
        for pattern in group.get(key, [])
    ]
    return patterns or None


def _edits_code(event: CanonicalToolEvent) -> bool:
    if not event.file_path:
        return True
    path = Path(event.file_path)
    root = Path(event.workspace_root or ".").resolve()
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return False
    else:
        relative = path.as_posix()
    return is_code(relative, _code_patterns(event.workspace_root))


def _evaluate_work_context(event: CanonicalToolEvent) -> PolicyDecision:
    if _is_bootstrap_or_repair(event.command):
        return PolicyDecision.allow()
    try:
        config = load_config(Path(event.workspace_root))
        if not config.tracking_enabled:
            return PolicyDecision.allow()
        if not event.branch:
            return PolicyDecision.deny(
                "A ticket branch is required before governed changes."
            )
        tracker = tracker_adapter(config.tracker)
        key = tracker.resolve_branch_key(event.branch)
        if not key:
            return PolicyDecision.deny(
                "Branch does not match the configured work-item convention and cannot be mapped to a tracker item."
            )
        item = tracker.get_work_item(_provider_ref(config.tracker, key))
        if item.state.value != "in_progress":
            return PolicyDecision.deny(
                f"Work item {item.key} must be in progress before code changes are allowed."
            )
        kinds = {
            _artifact_kind(artifact.kind)
            for artifact in tracker.list_artifacts(item.id)
        }
        if not (
            {
                "spec",
                "tech_spec",
                "tech-spec",
                "design_doc",
                "design-doc",
                "implementation_plan",
                "implementation-plan",
                "bugfix_spec",
                "bugfix-spec",
            }
            & kinds
        ):
            return PolicyDecision.deny(
                f"Work item {item.key} has no accepted specification artifact."
            )
        return PolicyDecision.allow()
    except IntegrationError as exc:
        return PolicyDecision.deny(
            f"Workflow integration unavailable ({exc.code}): {exc}"
        )
    except (OSError, ValueError) as exc:
        return PolicyDecision.deny(
            f"Workflow policy could not validate the current work item: {exc}"
        )


def _created_branch(argv: list[str]) -> str:
    """The branch a `git checkout -b` / `git switch -c` would create, or ``""``."""
    if not argv or argv[0] not in {"checkout", "switch"}:
        return ""
    for flag in ("-b", "-B", "-c", "-C", "--create"):
        if flag in argv:
            index = argv.index(flag)
            if index + 1 < len(argv):
                return argv[index + 1]
    return ""


def _validate_checkout_convention(command: str, project_root: str) -> PolicyDecision:
    targets = [name for name in map(_created_branch, git_commands(command)) if name]
    if not targets:
        return PolicyDecision.allow()
    target = targets[0]
    try:
        config = load_config(Path(project_root))
        if not config.tracking_enabled:
            return PolicyDecision.allow()
        tracker = tracker_adapter(config.tracker)
        if not tracker.resolve_branch_key(target):
            return PolicyDecision.deny(
                "Branch does not match the convention selected during workflow bootstrap."
            )
    except IntegrationError as exc:
        return PolicyDecision.deny(
            f"Workflow integration unavailable ({exc.code}): {exc}"
        )
    except (OSError, ValueError) as exc:
        return PolicyDecision.deny(
            f"Workflow policy could not validate the branch convention: {exc}"
        )
    return PolicyDecision.allow()


def _evaluate_completion(event: CanonicalToolEvent) -> PolicyDecision:
    try:
        config = load_config(Path(event.workspace_root))
        if not config.tracking_enabled:
            return PolicyDecision.allow()
        tracker = tracker_adapter(config.tracker)
        key = tracker.resolve_branch_key(event.branch)
        if not key:
            return PolicyDecision.deny(
                "Cannot complete a work item without a mapped ticket branch."
            )
        item = tracker.get_work_item(_provider_ref(config.tracker, key))
        kinds = {
            _artifact_kind(artifact.kind)
            for artifact in tracker.list_artifacts(item.id)
        }
        missing = {"resolution_report", "verification", "pull_request"} - kinds
        if missing:
            return PolicyDecision.deny(
                f"Cannot mark {item.key} done; missing artifacts: {', '.join(sorted(missing))}."
            )
        return PolicyDecision.allow()
    except IntegrationError as exc:
        return PolicyDecision.deny(
            f"Workflow integration unavailable ({exc.code}): {exc}"
        )


def _provider_ref(tracker_config: dict[str, Any], key: str) -> str:
    if tracker_config.get("adapter") == "azure_devops" and key.lower().startswith(
        "ab-"
    ):
        return key[3:]
    return key


def _artifact_kind(kind: str) -> str:
    normalized = str(kind).strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "pr": "pull_request",
        "pullrequest": "pull_request",
        "resolution": "resolution_report",
        "verification_report": "verification",
        "technical_specification": "tech-spec",
    }.get(normalized, normalized)


def _arguments(payload: dict[str, Any]) -> dict[str, Any]:
    return (
        payload.get("tool_input")
        or payload.get("toolInput")
        or payload.get("arguments")
        or payload.get("args")
        or {}
    )


def _normalized_tool_name(name: str) -> str:
    return name.rsplit("__", 1)[-1].rsplit("/", 1)[-1]


def _is_mutating_git(command: str) -> bool:
    return any(argv and argv[0] in _MUTATING_GIT for argv in git_commands(command))


def _is_bootstrap_or_repair(command: str | None) -> bool:
    text = command or ""
    return "scripts/harness/bootstrap.py" in text or "workflow-integrations" in text
