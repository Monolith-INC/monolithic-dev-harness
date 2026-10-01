from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from spec_runtime import SPEC_KINDS

from core.result import Err, Failure, Ok, Result, bind, fmap, recover
from harness import sessions, settings, state
from harness.local_artifacts import approved_kinds_for, artifacts_dir
from host_adapters import select_adapter
from host_adapters.hook_bridge import project_root_hint, should_emit_allow
from integrations import branches, registry
from integrations.contracts import LogicalState, TrackerOps, WorkItem
from policy import CanonicalToolEvent, PolicyDecision
from policy.commands import git_commands, is_code, writes_code
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
            file.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")
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
    decision = evaluate_event(event)
    if decision.is_denied():
        log_debug(f"DENIED: {decision.reason}")
    emit_decision(client, decision)
    return 0


def evaluate_event(event: CanonicalToolEvent) -> PolicyDecision:
    command = event.command or ""
    if event.kind == "shell":
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

    if event.tool_name == "tracker_transition_work_item":
        arguments = event.arguments or {}
        if arguments.get("state") == "done":
            return _evaluate_completion(event, str(arguments.get("ref", "")))
        return PolicyDecision.allow()

    if event.kind == "edit" and _edits_code(event):
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
    paths = event.file_paths or ((event.file_path,) if event.file_path else ())
    return not paths or any(_is_code_path(path, event.workspace_root) for path in paths)


def _is_code_path(file_path: str, workspace_root: str) -> bool:
    path = Path(file_path)
    root = Path(workspace_root or ".").resolve()
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return False
    else:
        relative = path.as_posix()
    return is_code(relative, _code_patterns(workspace_root))


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
    return bind(
        _active_session(root),
        lambda session: bind(
            registry.open_selected(root, settings.load(root)),
            lambda ops: fmap(
                ops.get_work_item(session.work_item),
                lambda item: (session, ops, item),
            ),
        ),
    )


def _active_session(root: Path) -> Result[sessions.Session]:
    match sessions.resolve(root):
        case sessions.Bound(session) if session.phase == sessions.Phase.ACTIVE:
            return Ok(session)
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
    boundary = "push" in {
        command[0] for command in git_commands(event.command or "") if command
    }
    return _decision(
        bind(
            _active_session(root),
            lambda session: (
                recover(
                    _snapshot_ready(root.resolve(), session),
                    lambda _: _live_ready(root),
                )
                if session.readiness_verified_at and not boundary
                else _live_ready(root)
            ),
        )
    )


def _live_ready(root: Path) -> Result[None]:
    return bind(
        _session_item(root),
        lambda found: _ready(root.resolve(), found[1], found[2]),
    )


def _snapshot_ready(root: Path, session: sessions.Session) -> Result[None]:
    """Readiness pinned when the session started. Ordinary edits it covers never contact the
    tracker; anything it does not cover (a spec published later) is checked live."""
    match session.readiness_state:
        case LogicalState.IN_PROGRESS.value:
            return _has_spec(
                root,
                session.work_item,
                {_artifact_kind(kind) for kind in session.readiness_artifacts},
            )
        case _:
            return Err(
                _failure(
                    f"Work item {session.work_item} was not in progress when this session started."
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
            root, item.key, {_artifact_kind(artifact.kind) for artifact in found}
        ),
    )


def _has_spec(root: Path, key: str, kinds: set[str]) -> Result[None]:
    local = set(map(_artifact_kind, approved_kinds_for(root, key)))
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
        _failure(f"Work item {key} has no accepted specification artifact in {where}.")
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


def _is_mutating_git(command: str) -> bool:
    return any(argv and argv[0] in _MUTATING_GIT for argv in git_commands(command))


# A lone bootstrap invocation, and nothing chained to it, may run before any session exists.
_BOOTSTRAP = re.compile(
    r"\s*(?:(?:\S*/)?python3?\s+\S*scripts/harness/bootstrap\.py|(?:\S*/)?harness\s+bootstrap)"
    r"(?:\s+[^\s;&|`$()<>\\]+)*\s*"
)


def _is_bootstrap_or_repair(command: str | None) -> bool:
    return _BOOTSTRAP.fullmatch(command or "") is not None
