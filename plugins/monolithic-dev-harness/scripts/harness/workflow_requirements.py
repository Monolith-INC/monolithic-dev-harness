"""What the workflow requires before code changes and before a work item is done, checked.

The requirements, and the stage and skill that produce each one, come from the prepared-workflow
catalog (`config/prepared-workflows.json`): a stage's `requires` must hold before code changes,
and the verify stage's `completes` before its work item is marked done. This module only knows
how to check them. Nothing here reads version control: code is compared as content
(`code_content`) against the snapshot taken when the work session linked its work item.

Tracker facts that held are kept per work session and linked work item, so ordinary edits do not
contact the tracker; a requirement that is not known to hold is checked live every time.
"""

from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.result import Err, Failure, Ok, Result, bind, fmap
from harness import (
    code_content,
    globs,
    local_artifacts,
    prepared_workflows,
    settings,
    state,
    work_sessions,
)
from integrations import registry
from integrations.contracts import LogicalState, TrackerOps, WorkItem, WorkItemKind

TRACKER_FACTS = "execution-facts.json"
# Failures that mean the tracker gave no answer at all, as opposed to an answer such as "not found".
UNREACHABLE = frozenset({"provider_unavailable", "not_configured"})
APPROVED_ANSWERS = frozenset({"approve", "approved", "yes", "approve and continue"})
_BUILDABLE = frozenset({WorkItemKind.USER_STORY, WorkItemKind.BUG})
# Facts that, once they held, are reused while the link holds. Code evidence never is.
_REMEMBERED = frozenset({"work_item_started", "tasks_parented", "plan_approved"})


@dataclass(frozen=True)
class Gate:
    name: str
    stage: str
    field: str  # the stage's list in the catalog: `requires` or `completes`
    action: str  # what waits, as the agent is told


CODE_CHANGE = Gate("code-change", "execution", "requires", "Code changes")
COMPLETION = Gate("completion", "verify", "completes", "Marking the work item done")
GATES = {gate.name: gate for gate in (CODE_CHANGE, COMPLETION)}


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


class _Wrong(Exception):
    """A requirement does not hold; the message says what was found."""


def link(repo: Path, session_id: str, work_item: str) -> Result[work_sessions.Session]:
    """Link the work session to its Story or Bug and snapshot the code as it is now.

    The snapshot is kept while the same item stays linked, so linking again cannot hide changes.
    """
    return bind(
        work_sessions.link(repo, session_id, work_item),
        lambda session: fmap(_snapshot(repo, session), lambda _: session),
    )


def _snapshot(repo: Path, session: work_sessions.Session) -> Result[None]:
    if code_content.baseline(session.folder, session.work_item) is not None:
        return Ok(None)
    try:
        code_content.save_baseline(
            session.folder, session.work_item, code_content.files(repo)
        )
    except OSError as exc:
        return Err(
            Failure("session_unwritable", f"could not record the code baseline: {exc}")
        )
    return Ok(None)


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
        prepared_workflows.stage_requirements(gate.stage, field=gate.field),
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
    key = session.work_item if session is not None else ""
    found: dict[
        str, str | None
    ] = {}  # requirement id -> None when met, else what is wrong
    unreachable = ""
    entries = {entry["id"]: entry for entry in required}
    match session, key:
        case None, _:
            found["work_item_linked"] = "no active work session is selected"
        case _, "":
            found["work_item_linked"] = f"work session {session.id} names no work item"
        case _, linked if work_item and work_item.upper() != linked.upper():
            found["work_item_linked"] = (
                f"work session {session.id} implements {linked}, not {work_item}"
            )
        case _:
            context = _Context(repo, session, key)
            try:
                found.update(context.check(tuple(entries)))
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


# --- one evaluation ------------------------------------------------------------------------------


@dataclass
class _Context:
    """What one evaluation reads, each part read at most once."""

    repo: Path
    session: work_sessions.Session
    key: str
    _found: dict[str, Any] = field(default_factory=dict)

    def check(self, ids: tuple[str, ...]) -> dict[str, str | None]:
        remembered = _known_facts(self.session, self.key)
        facts: dict[str, str | None] = {}
        for rid in ids:
            check = CHECKS.get(rid)
            if check is None:
                facts[rid] = "the harness has no check for this requirement"
            elif rid in remembered:
                facts[rid] = None
            else:
                try:
                    facts[rid] = check(self)
                except _Wrong as wrong:
                    facts[rid] = str(wrong)
        newly = {r for r, wrong in facts.items() if wrong is None} & _REMEMBERED
        if newly - remembered:
            _remember(self.session, self.key, remembered | newly)
        return facts

    def _once(self, name: str, read: Callable[[], Any]) -> Any:
        if name not in self._found:
            self._found[name] = read()
        return self._found[name]

    @property
    def settings(self) -> settings.Settings:
        def read() -> settings.Settings:
            match settings.load(self.repo):
                case Ok(chosen):
                    return chosen
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
        def read() -> WorkItem:
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
                _kind(str(a.kind))
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
            baseline = code_content.baseline(self.session.folder, self.key)
            if baseline is None:
                raise _Wrong(
                    f"the code was not recorded when {self.key} was linked; link it with "
                    "`harness work-session link --work-item <key>` before changing code"
                )
            return code_content.changed(baseline, self.code)

        return self._once("changed", read)


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


def _kind(kind: str) -> str:
    normalized = kind.strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "pr": "pull_request",
        "pullrequest": "pull_request",
        "resolution": "resolution_report",
        "verification_report": "verification",
    }.get(normalized, normalized)


# --- the checks ----------------------------------------------------------------------------------


def _linked(context: _Context) -> str | None:
    return None  # reached only when the session links the work item


def _started(context: _Context) -> str | None:
    item = context.item
    if item.kind not in _BUILDABLE:
        return f"{item.key} is a {item.kind.value}; link the Story or Bug it belongs to"
    if item.state != LogicalState.IN_PROGRESS:
        return f"{item.key} is {item.state.value}, not in progress"
    return None


def _tasks(context: _Context) -> str | None:
    item = context.item
    children = _tracker(context.ops.list_children(item.id))
    tasks = [child for child in children if child.kind is WorkItemKind.TASK]
    stray = [t.key for t in tasks if t.parent_id not in {item.id, item.key}]
    if not tasks:
        return f"{item.key} has no Tasks in the tracker"
    if stray:
        return f"Tasks {', '.join(stray)} do not name {item.key} as their parent"
    return None


def _plan(context: _Context) -> str | None:
    if _approved_plan_note(context.repo, context.key) or _approved_bundle(
        context.repo, context.session, context.key
    ):
        return None
    return (
        None
        if "implementation_plan" in context.artifact_kinds()
        else f"no approved implementation plan names {context.key}, in the tracker or as an "
        "approved note in the artifacts path"
    )


def _tests_with_code(context: _Context) -> str | None:
    for group in context.settings.tests_required:
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
        for guard in context.settings.guarded_paths
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
        code_content.applicable_checks(context.settings, context.changed)
        - state.passed_checks(context.repo, context.digest)
    )
    return (
        f"checks {missing} have not passed on the code as it is now "
        "(run scripts/harness/checks.py)"
        if missing
        else None
    )


def _review(context: _Context) -> str | None:
    if not context.settings.require_review_verdict:
        return None
    return (
        None
        if state.review_verdict(context.repo, context.digest) == "ready"
        else "no `ready` review verdict for the code as it is now (the review stage records "
        "it with scripts/harness/review_verdict.py)"
    )


def _artifact(kind: str, label: str) -> Callable[[_Context], str | None]:
    def check(context: _Context) -> str | None:
        return (
            None
            if kind in context.artifact_kinds()
            else f"{context.key} has no {label} artifact in the tracker"
        )

    return check


def _pull_request(context: _Context) -> str | None:
    chosen = context.settings
    if not chosen.git_delivery or chosen.scm.name == "local":
        return None  # no pull request is part of this project's delivery
    return _artifact("pull_request", "pull request")(context)


CHECKS: dict[str, Callable[[_Context], str | None]] = {
    "work_item_linked": _linked,
    "tasks_parented": _tasks,
    "plan_approved": _plan,
    "work_item_started": _started,
    "tests_with_code": _tests_with_code,
    "guarded_paths_verified": _guarded_paths,
    "checks_passed": _checks,
    "review_ready": _review,
    "resolution_reported": _artifact("resolution_report", "resolution report"),
    "verification_recorded": _artifact("verification", "verification"),
    "pull_request_linked": _pull_request,
}


# --- remembered tracker facts --------------------------------------------------------------------


def _known_facts(session: work_sessions.Session, key: str) -> set[str]:
    match state.read_json(session.folder / TRACKER_FACTS):
        case {"work_item": str() as linked, "met": list() as met} if linked == key:
            return {str(rid) for rid in met} & _REMEMBERED
        case _:
            return set()


def _remember(session: work_sessions.Session, key: str, met: set[str]) -> None:
    # The facts are only a shortcut; if they cannot be saved, the next check asks the tracker.
    with contextlib.suppress(OSError):
        state.write_json(
            session.folder / TRACKER_FACTS, {"work_item": key, "met": sorted(met)}
        )


# --- approved plans kept locally -----------------------------------------------------------------


def _is_plan(kind: str) -> bool:
    return _kind(kind) == "implementation_plan"


def _approved_plan_note(repo: Path, key: str) -> bool:
    """A note of type implementation-plan for `key` that the user approved as it reads now."""
    return any(_is_plan(kind) for kind in local_artifacts.approved_kinds_for(repo, key))


def _approved_bundle(repo: Path, session: work_sessions.Session, key: str) -> bool:
    """The session's last implementation-confirm answer approved its bundle, which is unchanged
    and published this work item."""
    answers = [
        entry
        for entry in (
            *(state.read_json(session.folder / "decision-history.json") or {}).get(
                "answers", []
            ),
            state.read_json(session.folder / "decision.json") or {},
        )
        if isinstance(entry, Mapping)
        and entry.get("gate") == "implementation-confirm"
        and entry.get("status") == "answered"
    ]
    published = (state.read_json(session.folder / "tracker-published.json") or {}).get(
        "keys", {}
    )
    return (
        bool(answers)
        and _approves(answers[-1])
        and _unchanged(repo, answers[-1].get("artifacts"))
        and isinstance(published, Mapping)
        and key in published.values()
    )


def _approves(entry: Mapping[str, Any]) -> bool:
    return (
        entry.get("approval") is True
        and str(entry.get("answer", "")).strip().casefold() in APPROVED_ANSWERS
    )


def _unchanged(repo: Path, artifacts: object) -> bool:
    match artifacts:
        case list() as entries if entries:
            return all(
                isinstance(entry, list)
                and len(entry) == 2
                and _digest(repo, str(entry[0])) == entry[1]
                for entry in entries
            )
        case _:
            return False


def _digest(repo: Path, relative: str) -> str:
    candidate = (repo / relative).resolve()
    try:
        if candidate.is_relative_to(repo.resolve()) and candidate.is_file():
            return hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError:
        pass
    return ""


# --- what the agent is told ----------------------------------------------------------------------


def refusal(report: Report) -> str:
    """The refusal, written for the agent: the next workflow step, not an error."""
    gate = report.gate
    status = f"`harness workflow requirements --gate {gate.name}` shows the same state."
    if report.unreachable:
        return (
            f"[harness] {gate.action} waits until the tracker answers, and it gave no answer: "
            f"{report.unreachable}. Retry once. If it still fails, tell the user the tracker is "
            f"unreachable and that typing `harness suspend` releases the harness checks. {status}"
        )
    first, *rest = report.missing
    lines = [
        f"[harness] {gate.action} waits for what the workflow catalog "
        f"(config/prepared-workflows.json) lists for the {gate.stage} stage. This refusal is for "
        "you, not for the user: continue the workflow from the step below. Ask the user only "
        "where that step itself asks for a decision.",
        f"Next: {first.how} (`{first.skill}` skill, {first.stage} stage). "
        f"{first.description} Found: {first.detail}.",
    ]
    lines += [f"Also missing: {m.id} — {m.detail} (`{m.skill}`)." for m in rest]
    lines.append(status)
    return "\n".join(lines)


def as_json(report: Report) -> dict[str, Any]:
    return {
        "gate": report.gate.name,
        "stage": report.gate.stage,
        "work_session": report.work_session,
        "work_item": report.work_item,
        "ready": report.ready,
        "met": list(report.met),
        "missing": [m.__dict__ for m in report.missing],
        "unreachable": report.unreachable,
    }
