from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from spec_runtime import SPEC_KINDS

from core.result import Err, Failure, Ok, Result, bind, fmap
from harness import sessions, settings, state
from harness.local_artifacts import approved_kinds_for, artifacts_dir
from host_adapters import (
    format_claude_decision,
    format_cursor_decision,
    parse_claude_payload,
    parse_cursor_payload,
)
from integrations import branches, registry
from integrations.contracts import LogicalState, TrackerOps, WorkItem
from policy import CanonicalToolEvent, PolicyDecision
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


def run(client: str, input_data: dict[str, Any], project_root: str = "") -> int:
    """Evaluate one host event. `project_root` is the checkout the call happens in; the hook
    passes the one it found from the payload, so sessions are checked where the edit is."""
    project_root = project_root or get_project_root()
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
            return _evaluate_completion(event, str(arguments.get("ref", "")))
        return PolicyDecision.allow()

    if event.tool_name in _WRITE_TOOLS and _edits_code(event):
        return _evaluate_work_context(event)
    return PolicyDecision.allow()


def _code_patterns(project_root: str) -> list[str] | None:
    """The settings' source and test globs: the files "spec before code" covers.

    `None` (every file but git's and the harness's) when the settings name none or cannot be read.
    """
    match settings.load(Path(project_root)):
        case Ok(chosen):
            patterns = [
                pattern
                for group in chosen.tests_required
                for pattern in (*group.source, *group.tests)
            ]
            return patterns or None
        case Err():
            return None


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


def _decision(result: Result[None]) -> PolicyDecision:
    match result:
        case Ok():
            return PolicyDecision.allow()
        case Err(failure):
            return PolicyDecision.deny(failure.message)


def _enforced(root: Path) -> bool:
    return state.tracking_mode(root) == "enforced"


def _session_item(root: Path) -> Result[tuple[sessions.Session, TrackerOps, WorkItem]]:
    """This checkout's active session, the tracker, and the session's work item as the tracker has it."""
    match sessions.resolve(root):
        case sessions.Bound(session) if session.phase == sessions.Phase.ACTIVE:
            return bind(
                registry.open_selected(root, settings.load(root)),
                lambda ops: fmap(
                    ops.get_work_item(session.work_item),
                    lambda item: (session, ops, item),
                ),
            )
        case sessions.Bound(session):
            return Err(
                _failure(
                    f"session {session.id} for {session.work_item} is {session.phase.value}; resume it first"
                )
            )
        case sessions.Unbound(reason) | sessions.Broken(reason):
            return Err(
                _failure(
                    f"governed changes need an active session: {reason}. Start one with "
                    "`harness session start <work item>` on the work item's branch."
                )
            )


def _failure(message: str) -> Failure:
    return Failure("workflow_policy", message)


def _evaluate_work_context(event: CanonicalToolEvent) -> PolicyDecision:
    root = Path(event.workspace_root or ".")
    if _is_bootstrap_or_repair(event.command) or not _enforced(root):
        return PolicyDecision.allow()
    return _decision(
        bind(
            _session_item(root),
            lambda found: _ready(root.resolve(), found[1], found[2]),
        )
    )


def _ready(root: Path, ops: TrackerOps, item: WorkItem) -> Result[None]:
    if item.state != LogicalState.IN_PROGRESS:
        return Err(
            _failure(
                f"Work item {item.key} must be in progress before code changes are allowed."
            )
        )
    return bind(
        ops.list_artifacts(item.id),
        lambda found: _has_spec(
            root, item, {_artifact_kind(artifact.kind) for artifact in found}
        ),
    )


def _has_spec(root: Path, item: WorkItem, kinds: set[str]) -> Result[None]:
    local = set(map(_artifact_kind, approved_kinds_for(root, str(item.key))))
    if SPEC_ARTIFACT_KINDS & (kinds | local):
        return Ok(None)
    folder = artifacts_dir(root)
    where = (
        "the tracker"
        if folder is None
        else f"the tracker or under {folder} (a note there counts once it is marked "
        "`status: approved` and the user then approves it)"
    )
    return Err(
        _failure(
            f"Work item {item.key} has no accepted specification artifact in {where}."
        )
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
    root = Path(project_root)
    if not targets or not _enforced(root):
        return PolicyDecision.allow()
    return _decision(
        bind(
            settings.load(root),
            lambda chosen: bind(
                registry.selected(root, Ok(chosen)),
                lambda active: fmap(
                    branches.work_item_id(
                        chosen.branch_template,
                        active.manifest.ids.branch_key,
                        targets[0],
                    ),
                    lambda _: None,
                ),
            ),
        )
    )


def _evaluate_completion(event: CanonicalToolEvent, ref: str) -> PolicyDecision:
    root = Path(event.workspace_root or ".")
    if not _enforced(root):
        return PolicyDecision.allow()
    return _decision(
        bind(
            _session_item(root),
            lambda found: _complete(found[0], found[1], found[2], ref),
        )
    )


def _complete(
    session: sessions.Session, ops: TrackerOps, item: WorkItem, ref: str
) -> Result[None]:
    if ref.strip().upper() not in {item.id.upper(), item.key.upper()}:
        return Err(
            _failure(
                f"this checkout's session is for {item.key}; {ref} is completed from its own session."
            )
        )
    return bind(
        ops.list_artifacts(item.id),
        lambda found: _completion_evidence(
            item, {_artifact_kind(a.kind) for a in found}
        ),
    )


def _completion_evidence(item: WorkItem, kinds: set[str]) -> Result[None]:
    missing = {"resolution_report", "verification", "pull_request"} - kinds
    return (
        Err(
            _failure(
                f"Cannot mark {item.key} done; missing artifacts: {', '.join(sorted(missing))}."
            )
        )
        if missing
        else Ok(None)
    )


def _artifact_kind(kind: str) -> str:
    normalized = str(kind).strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "pr": "pull_request",
        "pullrequest": "pull_request",
        "resolution": "resolution_report",
        "verification_report": "verification",
        "technical_specification": "tech_spec",
    }.get(normalized, normalized)


# The kinds write-spec produces, plus the generic `spec`, in the form `_artifact_kind` gives them.
SPEC_ARTIFACT_KINDS = frozenset(map(_artifact_kind, (*SPEC_KINDS, "spec")))


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


# A lone bootstrap invocation, and nothing chained to it, may run before any session exists.
_BOOTSTRAP = re.compile(
    r"\s*(?:(?:\S*/)?python3?\s+\S*scripts/harness/bootstrap\.py|(?:\S*/)?harness\s+bootstrap)"
    r"(?:\s+[^\s;&|`$()<>\\]+)*\s*"
)


def _is_bootstrap_or_repair(command: str | None) -> bool:
    return _BOOTSTRAP.fullmatch(command or "") is not None
