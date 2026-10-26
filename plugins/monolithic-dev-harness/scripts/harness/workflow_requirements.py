"""What the workflow requires before code changes and before a work item is done, checked.

The requirements, and the stage and skill that produce each one, come from the route
(`route` in `config/prepared-workflows.json`, read by `harness.route`): everything the route does
for a Story before the step that performs a guarded action must hold before that action. This
module only knows how to check them. Nothing here reads version control: code is compared as content
(`code_content`) against the record taken when the work item was first linked.

The first requirement of both lists, `work_item_linked`, is the precondition the others are read
against. Tracker facts that held are kept per work session and linked work item, so ordinary edits
do not contact the tracker; a requirement not known to hold is checked live every time.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.result import Err, Failure, Ok, Result, fmap
from harness import (
    code_content,
    documents,
    globs,
    local_artifacts,
    prepared_workflows,
    refined,
    settings,
    state,
    work_sessions,
)
from integrations import registry
from integrations.contracts import (
    BUILDABLE_KINDS,
    LogicalState,
    TrackerOps,
    WorkItem,
    WorkItemKind,
)

LINK = "work_item_linked"
TRACKER_FACTS = "execution-facts.json"
# Failures that mean the tracker gave no answer at all, as opposed to an answer such as "not found".
UNREACHABLE = frozenset(
    {
        "provider_unavailable",
        "provider_exited",
        "provider_closed",
        "provider_timeout",
        "provider_read_failed",
        "gateway_unavailable",
        "not_configured",
    }
)


@dataclass(frozen=True)
class Gate:
    name: str
    action: str  # what waits, as the agent is told
    read: Callable[
        [], Result[tuple[dict[str, str], ...]]
    ]  # its requirements from the catalog


CODE_CHANGE = Gate(
    "code-change",
    "Code changes",
    lambda: prepared_workflows.guard_requirements("code-change"),
)
COMPLETION = Gate(
    "completion",
    "Marking the work item done",
    lambda: prepared_workflows.guard_requirements("completion"),
)
STORY_START = Gate(
    "story-start",
    "Moving the Story to in progress",
    lambda: prepared_workflows.guard_requirements("story-start"),
)
TASKS_PUBLISH = Gate(
    "tasks-publish",
    "Creating the Story's Tasks",
    lambda: prepared_workflows.guard_requirements("tasks-publish"),
)
GATES = {
    gate.name: gate for gate in (CODE_CHANGE, COMPLETION, STORY_START, TASKS_PUBLISH)
}


@dataclass(frozen=True)
class Missing:
    id: str
    description: str
    stage: str
    skill: str
    how: str
    detail: str


@dataclass(frozen=True)
class Report:
    gate: Gate
    work_session: str | None
    work_item: str
    met: tuple[str, ...]
    missing: tuple[Missing, ...]
    unreachable: str = ""

    @property
    def ready(self) -> bool:
        return not self.missing and not self.unreachable


class _Unreachable(Exception):
    """The tracker gave no answer."""


UnreachableTracker = _Unreachable


class _Wrong(Exception):
    """A requirement does not hold; the message says what was found."""


def evaluate(
    repo: Path,
    session_id: str | None,
    gate: Gate = CODE_CHANGE,
    work_item: str | None = None,
) -> Result[Report]:
    """What the gate requires of this work session, and which of those are missing.

    `work_item`, when given, is the item the gated action is about; the session must link it.
    """
    return fmap(
        gate.read(),
        lambda required: _evaluate(repo, session_id, gate, required, work_item),
    )


def _evaluate(
    repo: Path,
    session_id: str | None,
    gate: Gate,
    required: tuple[dict[str, str], ...],
    work_item: str | None,
) -> Report:
    session = _active(repo, session_id)
    entries = {entry["id"]: entry for entry in required}
    found: dict[
        str, str | None
    ] = {}  # requirement id -> None when met, else what is wrong
    unreachable = ""
    if LINK in entries:
        # The action is the linked item's own (code changes, marking it done).
        key = session.work_item if session is not None else ""
        wrong = _unlinked(session, work_item)
    else:
        # The action is about an item before any session links it (its Tasks, its start).
        key = work_item or ""
        wrong = None if key else "the action names no work item"
    if wrong is not None:
        found[LINK if LINK in entries else next(iter(entries))] = wrong
    else:
        if LINK in entries:
            found[LINK] = None
        try:
            found.update(_Context(repo, session, key).check(tuple(entries)))
        except _Unreachable as exc:
            unreachable = str(exc)
    return Report(
        gate=gate,
        work_session=session.id if session is not None else None,
        work_item=key,
        met=tuple(rid for rid in entries if rid in found and found[rid] is None),
        missing=tuple(
            Missing(detail=str(found[rid]), **entry)
            for rid, entry in entries.items()
            if found.get(rid) is not None
        ),
        unreachable=unreachable,
    )


def _unlinked(
    session: work_sessions.Session | None, work_item: str | None
) -> str | None:
    """Why the precondition fails, or None when the session links the item the action is about."""
    match session:
        case None:
            return "no active work session is selected"
        case _ if not session.work_item:
            return f"work session {session.id} names no work item"
        case _ if work_item and work_item.upper() != session.work_item.upper():
            return f"work session {session.id} implements {session.work_item}, not {work_item}"
        case _:
            return None


def _active(repo: Path, session_id: str | None) -> work_sessions.Session | None:
    match session_id and work_sessions.require_active(repo, session_id):
        case Ok(session):
            return session
        case _:
            return None


def linked_session(repo: Path, work_item: str) -> str | None:
    """The active work session that implements `work_item`, if exactly one does."""
    match work_sessions.list_sessions(repo):
        case Ok(sessions):
            matching = [
                s.id
                for s in sessions
                if s.status == work_sessions.Status.ACTIVE
                and s.work_item.upper() == work_item.upper()
            ]
            return matching[0] if len(matching) == 1 else None
        case _:
            return None


def artifact_kind(kind: str) -> str:
    """One spelling per artifact kind, however a tracker or a person wrote it."""
    normalized = str(kind).strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "pr": "pull_request",
        "pullrequest": "pull_request",
        "resolution": "resolution_report",
        "verification_report": "verification",
    }.get(normalized, normalized)


# --- one evaluation ------------------------------------------------------------------------------


@dataclass
class _Context:
    """What one evaluation reads, each part read at most once."""

    repo: Path
    session: work_sessions.Session | None
    key: str
    _found: dict[str, Any] = field(default_factory=dict)

    def check(self, ids: tuple[str, ...]) -> dict[str, str | None]:
        remembered = _known_facts(self.session, self.key)
        facts: dict[str, str | None] = {}
        for rid in (rid for rid in ids if rid != LINK):
            check = CHECKS.get(rid)
            if check is None:
                facts[rid] = "the harness has no check for this requirement"
            elif rid in remembered and check.lasting:
                facts[rid] = None
            else:
                try:
                    facts[rid] = check.read(self)
                except _Wrong as wrong:
                    facts[rid] = str(wrong)
        held = {
            rid
            for rid, wrong in facts.items()
            if wrong is None and rid in CHECKS and CHECKS[rid].lasting
        }
        if held - remembered:
            _remember(self.session, self.key, remembered | held)
        return facts

    def _once(self, name: str, read: Callable[[], Any]) -> Any:
        if name not in self._found:
            self._found[name] = read()
        return self._found[name]

    @property
    def chosen(self) -> settings.Settings:
        def read() -> settings.Settings:
            match settings.load(self.repo):
                case Ok(loaded):
                    return loaded
                case Err(failure):
                    raise _Wrong(f"the settings cannot be read: {failure.message}")

        return self._once("settings", read)

    @property
    def ops(self) -> TrackerOps:
        return self._once(
            "ops",
            lambda: _answer(
                registry.open_selected(self.repo, settings.load(self.repo))
            ),
        )

    @property
    def item(self) -> WorkItem:
        def read() -> WorkItem | Failure:
            match self.ops.get_work_item(self.key):
                case Err(failure) if failure.code in UNREACHABLE:
                    raise _Unreachable(failure.message)
                case Err(failure):
                    return failure
                case Ok(item):
                    return item

        found = self._once("item", read)
        if not isinstance(found, WorkItem):
            raise _Wrong(f"the tracker could not read {self.key}: {found.message}")
        return found

    def artifact_kinds(self) -> set[str]:
        return self._once(
            "artifacts",
            lambda: {
                artifact_kind(a.kind)
                for a in _tracker(self.ops.list_artifacts(self.item.id))
            },
        )

    @property
    def code(self) -> dict[str, str]:
        return self._once("code", lambda: code_content.files(self.repo))

    @property
    def digest(self) -> str:
        return self._once("digest", lambda: code_content.digest(self.code))

    @property
    def changed(self) -> tuple[str, ...]:
        def read() -> tuple[str, ...]:
            baseline = code_content.baseline(self.repo, self.key)
            if baseline is None:
                raise _Wrong(
                    f"the code was not recorded when {self.key} was linked; link it with "
                    "`harness work-session link --work-item <key>` before changing code"
                )
            return code_content.changed(baseline, self.code)

        return self._once("changed", read)


def context(
    repo: Path, session: work_sessions.Session, key: str, ops: TrackerOps | None = None
) -> _Context:
    """A reader for one work item's requirements; `ops` reuses an open tracker connection."""
    found = _Context(repo, session, key)
    if ops is not None:
        found._found["ops"] = ops
    return found


def _answer(result: Result[Any]) -> Any:
    match result:
        case Ok(value):
            return value
        case Err(failure) if failure.code in UNREACHABLE:
            raise _Unreachable(failure.message)
        case Err(failure):
            raise _Unreachable(f"{failure.code}: {failure.message}")


def _tracker(result: Result[Any]) -> Any:
    match result:
        case Err(failure) if failure.code in UNREACHABLE:
            raise _Unreachable(failure.message)
        case Err(failure):
            raise _Wrong(f"the tracker refused: {failure.message}")
        case Ok(value):
            return value


# --- the checks ----------------------------------------------------------------------------------


def _started(context: _Context) -> str | None:
    item = context.item
    if item.kind not in BUILDABLE_KINDS:
        return f"{item.key} is a {item.kind.value}; link the Story or Bug it belongs to"
    if item.state != LogicalState.IN_PROGRESS:
        return f"{item.key} is {item.state.value}, not in progress"
    return None


def _tasks(context: _Context) -> str | None:
    item = context.item
    children = _tracker(context.ops.list_children(item.id))
    tasks = [child for child in children if child.kind is WorkItemKind.TASK]
    stray = [t.key for t in tasks if not t.is_child_of(item)]
    if not tasks:
        return f"{item.key} has no Tasks in the tracker"
    if stray:
        return f"Tasks {', '.join(stray)} do not name {item.key} as their parent"
    return None


def _plan(context: _Context) -> str | None:
    match context.session:
        case work_sessions.Session(entry_item=str() as entry) if entry:
            from harness import plan_review
            from harness.workflow_evidence import history, option_id

            match any(
                record.get("gate") == "implementation-confirm"
                and record.get("status") == "answered"
                and option_id(record) == "approve"
                for record in history(context.session)
            ):
                case False:
                    return "Approve the implementation plan in this planning round before execution."
                case True:
                    return (
                        None
                        if plan_review.approved_source(context.repo, context.item)
                        else "The approved implementation plan does not match the current work-item requirements; revalidate it before execution."
                    )
        case _:
            pass
    if _approved_plan_note(context.repo, context.key):
        return None
    return (
        None
        if "implementation_plan" in context.artifact_kinds()
        else f"no approved implementation plan names {context.key}, in the tracker or as an "
        "approved note in the artifacts path"
    )


def _approved_plan_note(repo: Path, key: str) -> bool:
    """A note of type implementation-plan for `key` that the user approved as it reads now."""
    return any(
        artifact_kind(kind) == "implementation_plan"
        for kind in local_artifacts.approved_kinds_for(repo, key)
    )


def _refined(context: _Context) -> str | None:
    match refined.check(context.item):
        case Err(failure):
            return failure.message
        case _:
            return None


def _approved_note(kind: str, label: str) -> Callable[[_Context], str | None]:
    def read(context: _Context) -> str | None:
        kinds = {
            artifact_kind(found)
            for found in local_artifacts.approved_kinds_for(context.repo, context.key)
        }
        return (
            None
            if artifact_kind(kind) in kinds
            else f"no {label} naming {context.key} was approved as it reads now"
        )

    return read


def _manifest(context: _Context) -> str | None:
    match documents.document_path(
        context.repo, context.ops, context.key, "reading-manifest"
    ):
        case Ok(path) if path.is_file():
            return None
        case Ok(path):
            return f"the reading manifest {path} does not exist yet"
        case Err(failure):
            return failure.message


def _code_changed(context: _Context) -> str | None:
    return (
        None if context.changed else f"no code changed since {context.key} was linked"
    )


def _done(context: _Context) -> str | None:
    state_now = context.item.state
    return (
        None
        if state_now == LogicalState.DONE
        else f"{context.key} is {state_now.value}"
    )


def _tests_with_code(context: _Context) -> str | None:
    for group in context.chosen.tests_required:
        sources = globs.select(context.changed, list(group.source), list(group.exclude))
        if sources and not globs.select(context.changed, list(group.tests)):
            return (
                f"{len(sources)} source file(s) changed (e.g. {sources[0]}) and no test "
                f"matching {list(group.tests)} changed with them"
            )
    return None


def _guarded_paths(context: _Context) -> str | None:
    unmet = [
        guard
        for guard in context.chosen.guarded_paths
        if globs.select(context.changed, [guard.path])
        and not (
            guard.name in state.passed_checks(context.repo, context.digest)
            if guard.kind == "check"
            else state.has_manual(context.repo, guard.name, context.digest)
        )
    ]
    return (
        "; ".join(
            f"{guard.path} changed and its check `{guard.name}` has not passed on the code as it "
            "is now (run scripts/harness/checks.py)"
            if guard.kind == "check"
            else f"{guard.path} changed and the user has not confirmed `{guard.name}` by hand "
            f"for the code as it is now (`harness manual-check {guard.name} ok`)"
            for guard in unmet
        )
        or None
    )


def _checks(context: _Context) -> str | None:
    missing = sorted(
        code_content.applicable_checks(context.chosen, context.changed)
        - state.passed_checks(context.repo, context.digest)
    )
    return (
        f"checks {missing} have not passed on the code as it is now "
        "(run scripts/harness/checks.py)"
        if missing
        else None
    )


def _review(context: _Context) -> str | None:
    if not context.chosen.require_review_verdict:
        return None
    return (
        None
        if state.review_verdict(context.repo, context.digest) == "ready"
        else "no `ready` review verdict for the code as it is now (the review stage records "
        "it with scripts/harness/review_verdict.py)"
    )


def _artifact(kind: str, label: str) -> Callable[[_Context], str | None]:
    def read(context: _Context) -> str | None:
        return (
            None
            if kind in context.artifact_kinds()
            else f"{context.key} has no {label} artifact in the tracker"
        )

    return read


@dataclass(frozen=True)
class _Check:
    read: Callable[[_Context], str | None]
    lasting: bool = (
        False  # a tracker fact that, once it held, is reused while the link holds
    )


CHECKS: dict[str, _Check] = {
    "story_refined": _Check(_refined, lasting=True),
    "risk_approved": _Check(_approved_note("risk-assessment", "risk document")),
    "verification_planned": _Check(
        _approved_note("verification-plan", "verification document")
    ),
    "manifest_built": _Check(_manifest, lasting=True),
    "code_changed": _Check(_code_changed),
    "story_done": _Check(_done),
    "tasks_parented": _Check(_tasks, lasting=True),
    "plan_approved": _Check(_plan),
    "work_item_started": _Check(_started, lasting=True),
    "tests_with_code": _Check(_tests_with_code),
    "guarded_paths_verified": _Check(_guarded_paths),
    "checks_passed": _Check(_checks),
    "review_ready": _Check(_review),
    "resolution_reported": _Check(_artifact("resolution_report", "resolution report")),
    "verification_recorded": _Check(_artifact("verification", "verification")),
}
CHECKED = frozenset({LINK, *CHECKS})  # every requirement id this module knows


# --- remembered tracker facts --------------------------------------------------------------------


def _known_facts(session: work_sessions.Session | None, key: str) -> set[str]:
    if session is None:
        return set()
    match state.read_json(session.folder / TRACKER_FACTS):
        case {"work_item": str() as linked, "met": list() as met} if linked == key:
            return {str(rid) for rid in met if rid in CHECKS and CHECKS[rid].lasting}
        case _:
            return set()


def _remember(session: work_sessions.Session | None, key: str, met: set[str]) -> None:
    # The facts are only a shortcut; if they cannot be saved, the next check asks the tracker.
    if session is None:
        return
    with contextlib.suppress(OSError):
        state.write_json(
            session.folder / TRACKER_FACTS, {"work_item": key, "met": sorted(met)}
        )


# --- what the agent is told ----------------------------------------------------------------------


def refusal(report: Report) -> str:
    """The refusal, written for the agent: the next workflow step, not an error."""
    gate = report.gate
    status = f"`harness workflow requirements --gate {gate.name}` shows the same state."
    if report.unreachable:
        return (
            f"[harness] {gate.action} waits until the tracker answers, and it gave no answer: "
            f"{report.unreachable}. Recover/reload the owning workflow-integrations gateway before another bounded read; "
            f"do not start another provider or replay an uncertain write. Local status and lifecycle recovery remain available. {status}"
        )
    first, *rest = report.missing
    lines = [
        f"[harness] {gate.action} waits for what the workflow route requires before it. This "
        "refusal is for you, not for the user: run `harness next` and do the step it gives. "
        "Ask the user only where that step itself asks for a decision.",
        f"Next: {first.how} (`{first.skill}` skill, {first.stage} stage). "
        f"{first.description} Found: {first.detail}.",
    ]
    lines += [f"Also missing: {m.id} — {m.detail} (`{m.skill}`)." for m in rest]
    lines.append(status)
    return "\n".join(lines)


def as_json(report: Report) -> dict[str, Any]:
    return {
        "gate": report.gate.name,
        "work_session": report.work_session,
        "work_item": report.work_item,
        "ready": report.ready,
        "met": list(report.met),
        "missing": [m.__dict__ for m in report.missing],
        "unreachable": report.unreachable,
    }
