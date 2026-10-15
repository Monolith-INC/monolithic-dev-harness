from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from core.result import Err, Failure, Ok, Result, bind, fmap
from harness import (
    code_content,
    settings,
    state,
    work_sessions,
    workflow_requirements,
)
from host_adapters import select_adapter
from host_adapters.hook_bridge import project_root_hint, should_emit_allow
from integrations import branches, registry
from integrations.contracts import LogicalState, TrackerOps, WorkItem, WorkItemKind
from policy import CanonicalToolEvent, PolicyDecision
from policy.commands import escapes_checkout, git_commands, is_code, writes_code
from policy.git_branch_guard import evaluate_git_branch_guard

LOG_FILE = "/tmp/harness_hook_debug.log"
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


def log_debug(message: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"{datetime.now(UTC).isoformat()} - {message}\n")
    except OSError:
        pass


def get_project_root(client: str) -> str:
    value = project_root_hint(client)
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


def emit_decision(client: str, decision: PolicyDecision) -> None:
    if not decision.is_denied() and not should_emit_allow(client):
        return
    _, formatter = select_adapter(client)
    print(json.dumps(formatter(decision)))


def run(client: str, input_data: dict[str, Any], project_root: str = "") -> int:
    """Evaluate one host event. `project_root` is the checkout the call happens in; the hook
    passes the one it found from the payload, so sessions are checked where the edit is."""
    project_root = project_root or get_project_root(client)
    parser, _ = select_adapter(client)
    event = parser(input_data, project_root=project_root)
    event = CanonicalToolEvent(
        **{**event.__dict__, "branch": current_branch(project_root)}
    )
    decision = evaluate_event(event, _work_session(project_root, client, input_data))
    if decision.is_denied():
        log_debug(f"DENIED: {decision.reason}")
    emit_decision(client, decision)
    return 0


def _work_session(
    project_root: str, client: str, payload: dict[str, Any]
) -> str | None:
    """The work session this host conversation is bound to, else the project's current one."""
    from host_adapters import work_session_context

    root = Path(project_root)
    match work_session_context.for_payload(root, client, payload):
        case Ok(str() as bound):
            return bound
        case _:
            return work_sessions.current(root)


def evaluate_event(
    event: CanonicalToolEvent, work_session_id: str | None = None
) -> PolicyDecision:
    # The decision gate and work-session binding run once, in harness/hook.py, before this.
    command = event.command or ""
    root = Path(event.workspace_root or ".")
    if event.kind == "shell":
        delivery = _git_delivery(root)
        if delivery:
            branch_decision = evaluate_git_branch_guard(command, event.workspace_root)
            if branch_decision.is_denied():
                return branch_decision
            checkout_decision = _validate_checkout_convention(
                command, event.workspace_root
            )
            if checkout_decision.is_denied():
                return checkout_decision
        if writes_code(
            command,
            event.workspace_root,
            code_content.patterns(root),
            code_content.planning_folder(root),
        ):
            code_decision = _evaluate_code_change(event, work_session_id)
            if code_decision.is_denied():
                return code_decision
        if delivery and _is_mutating_git(command):
            return _evaluate_git_delivery(event, work_session_id)
        return PolicyDecision.allow()

    if event.tool_name == "tracker_transition_work_item":
        arguments = event.arguments or {}
        if arguments.get("state") == "done":
            return _evaluate_completion(
                event, str(arguments.get("ref", "")), work_session_id
            )
        return PolicyDecision.allow()

    if event.kind == "edit" and _edits_code(event):
        return _evaluate_code_change(event, work_session_id)
    return PolicyDecision.allow()


def _git_delivery(root: Path) -> bool:
    """Whether the user chose Git-based delivery; only then do rules about Git commands apply."""
    match settings.load(root):
        case Ok(chosen):
            return chosen.git_delivery
        case Err():
            return False


def _evaluate_code_change(
    event: CanonicalToolEvent, work_session_id: str | None
) -> PolicyDecision:
    """Code changes wait for the execution stage's requirements in the workflow catalog.

    Version control plays no part: the work session, the tracker, and the approvals decide.
    """
    root = Path(event.workspace_root or ".")
    if _is_bootstrap_or_repair(event.command) or not _enforced(root):
        return PolicyDecision.allow()
    return _gate(root, work_session_id or work_sessions.current(root))[0]


def _gate(
    root: Path,
    scope: str | None,
    gate: workflow_requirements.Gate = workflow_requirements.CODE_CHANGE,
    work_item: str | None = None,
) -> tuple[PolicyDecision, workflow_requirements.Report | None]:
    """The gate's decision and, when the catalog could be read, its report."""
    match workflow_requirements.evaluate(root, scope, gate, work_item):
        case Ok(report) if report.ready:
            return PolicyDecision.allow(), report
        case Ok(report):
            return PolicyDecision.deny(workflow_requirements.refusal(report)), report
        case Err(failure):
            return (
                PolicyDecision.deny(
                    f"[harness] the workflow catalog cannot be read ({failure.message}); "
                    f"{gate.action.lower()} stays blocked until the harness package is repaired."
                ),
                None,
            )


def _edits_code(event: CanonicalToolEvent) -> bool:
    paths = event.file_paths or ((event.file_path,) if event.file_path else ())
    return not paths or any(_is_code_path(path, event.workspace_root) for path in paths)


def _is_code_path(file_path: str, workspace_root: str) -> bool:
    path = Path(file_path)
    root = Path(workspace_root or ".").resolve()
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return escapes_checkout(file_path, root)
    else:
        try:
            relative = (root / path).resolve().relative_to(root).as_posix()
        except ValueError:
            return escapes_checkout(file_path, root)
    return is_code(
        relative,
        code_content.patterns(root),
        planning=code_content.planning_folder(root),
    )


def _decision(result: Result[None]) -> PolicyDecision:
    match result:
        case Ok():
            return PolicyDecision.allow()
        case Err(failure):
            return PolicyDecision.deny(failure.message)


def _enforced(root: Path) -> bool:
    return state.tracking_mode(root) == "enforced"


def _evaluate_git_delivery(
    event: CanonicalToolEvent, work_session_id: str | None
) -> PolicyDecision:
    """With Git-based delivery, a commit or push carries code: the code-change requirements hold,
    on a branch whose name carries the linked work item's key."""
    root = Path(event.workspace_root or ".")
    if _is_bootstrap_or_repair(event.command) or not _enforced(root):
        return PolicyDecision.allow()
    decision, report = _gate(root, work_session_id or work_sessions.current(root))
    if decision.is_denied() or report is None:
        return decision
    return _decision(_on_item_branch(root, event.branch, report.work_item))


def _on_item_branch(root: Path, branch: str, work_item: str) -> Result[None]:
    return bind(
        settings.load(root),
        lambda chosen: bind(
            registry.selected(root, Ok(chosen)),
            lambda active: bind(
                branches.work_item_id(
                    chosen.branch_template, active.manifest.ids.branch_key, branch
                )
                if branch
                else Err(Failure("workflow_policy", "HEAD is not on a branch")),
                lambda key: (
                    Ok(None)
                    if key.upper() == work_item.upper()
                    else Err(
                        Failure(
                            "workflow_policy",
                            f"branch {branch} is for {key}, but the work session implements "
                            f"{work_item}; commit and push on {work_item}'s branch",
                        )
                    )
                ),
            ),
        ),
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


def _evaluate_completion(
    event: CanonicalToolEvent, ref: str, work_session_id: str | None = None
) -> PolicyDecision:
    """A work item is done only when the workflow catalog's completion requirements hold.

    A Breakdown task closes on its planning receipt; another Task closes inside the work session
    that implements its Story or Bug; a Feature or Epic closes once its children are; a Story or
    Bug needs the catalog's `completion` list.
    """
    root = Path(event.workspace_root or ".")
    if not _enforced(root):
        return PolicyDecision.allow()
    found = bind(
        registry.open_selected(root, settings.load(root)),
        lambda ops: bind(
            ops.get_work_item(ref),
            lambda item: fmap(
                ops.list_artifacts(item.id), lambda artifacts: (ops, item, artifacts)
            ),
        ),
    )
    match found:
        case Err(failure):
            return PolicyDecision.deny(failure.message)
        case Ok((ops, item, artifacts)):
            pass
    receipts = tuple(
        a
        for a in artifacts
        if workflow_requirements.artifact_kind(a.kind) == "planning_completion"
    )
    if receipts:
        return _decision(fmap(_receipt_route(ops, item, receipts), lambda _: None))
    if item.kind is WorkItemKind.TASK:
        return _task_completion(root, ops, item)
    if item.kind in (WorkItemKind.FEATURE, WorkItemKind.EPIC):
        return _container_completion(ops, item, artifacts)
    scope = (
        work_session_id
        if _links(root, work_session_id, item)
        else workflow_requirements.linked_session(root, item.key)
    )
    return _gate(root, scope, workflow_requirements.COMPLETION, item.key)[0]


def _receipt_route(ops: TrackerOps, item: WorkItem, receipts: tuple) -> Result[object]:
    """A Breakdown task closes on its newest planning receipt; no work session is involved."""
    from policy.planning_completion import current, verify

    return bind(current(receipts), lambda receipt: verify(ops, item, receipt))


def _links(root: Path, work_session_id: str | None, item: WorkItem) -> bool:
    match work_session_id and work_sessions.select(root, work_session_id):
        case Ok(session):
            return session.work_item.upper() in {item.key.upper(), item.id.upper()}
        case _:
            return False


_CLOSED = frozenset({LogicalState.DONE, LogicalState.CANCELED})


def _container_completion(
    ops: TrackerOps, item: WorkItem, artifacts: tuple
) -> PolicyDecision:
    """A Feature or Epic is done once it has children, every one is done or cancelled (each was
    held to its own completion rules), and it holds its closing report."""
    match ops.list_children(item.id):
        case Err(failure):
            return PolicyDecision.deny(failure.message)
        case Ok(children):
            pass
    still_open = [child.key for child in children if child.state not in _CLOSED]
    reported = any(
        workflow_requirements.artifact_kind(a.kind) == "closing_report"
        for a in artifacts
    )
    match children, still_open, reported:
        case (), _, _:
            reason = f"{item.key} has no child work items to close it on"
        case _, [_, *_], _:
            reason = f"{', '.join(still_open)} under {item.key} not done yet"
        case _, _, False:
            reason = (
                "publish its closing evidence first with `tracker_publish_artifact` (kind "
                "`closing-report`; `finish-feature-development` skill)"
            )
        case _:
            return PolicyDecision.allow()
    return PolicyDecision.deny(
        f"[harness] {item.key} is marked done only when its children are: {reason}. This "
        "refusal is for you, not for the user."
    )


def _task_completion(root: Path, ops: TrackerOps, task: WorkItem) -> PolicyDecision:
    """A Task is done inside the work session that implements its parent Story or Bug."""
    match ops.get_work_item(task.parent_id) if task.parent_id else None:
        case Ok(parent) if workflow_requirements.linked_session(
            root, parent.key
        ) or workflow_requirements.linked_session(root, parent.id):
            return PolicyDecision.allow()
        case Ok(parent):
            owner = parent.key
        case _:
            owner = "its Story or Bug"
    return PolicyDecision.deny(
        f"[harness] Task {task.key} is marked done inside the work session that implements "
        f"{owner}. This refusal is for you, not for the user: link that work session with "
        "`harness work-session link --work-item <key>` (`start-ticket` skill), then mark the "
        "Task done."
    )


def _is_mutating_git(command: str) -> bool:
    return any(argv and argv[0] in _MUTATING_GIT for argv in git_commands(command))


# A lone bootstrap invocation, and nothing chained to it, may run before any session exists.
_BOOTSTRAP = re.compile(
    r"\s*(?:(?:\S*/)?python3?\s+\S*scripts/harness/bootstrap\.py|(?:\S*/)?harness\s+bootstrap)"
    r"(?:\s+[^\s;&|`$()<>\\]+)*\s*"
)


def _is_bootstrap_or_repair(command: str | None) -> bool:
    return _BOOTSTRAP.fullmatch(command or "") is not None
