"""The route's facts, read from one project and work session, and `harness next`.

`route.next_step` decides; this module only reads: the setup, the work session, the user's answers
in that session, the documents in the artifacts path and, through the tracker gateway, the items.
Each read happens at most once per call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, bind, err
from harness import (
    decisions,
    documents,
    gates,
    local_artifacts,
    questions,
    refined,
    route,
    settings,
    setup,
    work_sessions,
    workflow_requirements,
)
from integrations import registry
from integrations.contracts import (
    BUILDABLE_KINDS,
    LogicalState,
    TrackerOps,
    WorkItem,
    WorkItemKind,
)

PARENT_KINDS = frozenset({WorkItemKind.EPIC, WorkItemKind.FEATURE})
# The check facts about the work as a whole that `ProjectFacts` reads; Story facts are
# `workflow_requirements.CHECKS` and `work_item_linked`.
WORK_FACTS = frozenset(
    {
        "setup_ready",
        "entry_tracked",
        "entry_refined_now",
        "entry_is_parent",
        "any_published",
        "published_after_approach",
        "approach_drafted",
        "stories_exist",
        "entry_done",
        "methods_applied",
        "methods_selected",
    }
)
STORY_FACTS = frozenset({"work_item_linked", *workflow_requirements.CHECKS})
_APPROVED = {"plan-checkpoint": ("continue", "stop"), "publish-items": ("approve",)}


class Unreachable(Exception):
    """The tracker gave no answer, so the next step cannot be known."""


@dataclass
class ProjectFacts:
    """`route.Facts` for one project and work session."""

    repo: Path
    session: work_sessions.Session
    _cache: dict[Any, Any] = field(default_factory=dict)

    # --- the Facts protocol ---------------------------------------------------------------

    def check(self, fact: str, story: str | None) -> bool:
        key = (fact, story)
        if key not in self._cache:
            self._cache[key] = (
                self._work(fact) if story is None else self._story(fact, story)
            )
        return self._cache[key]

    def answer(self, gate: str) -> str | None:
        return self.answers().get(gate)

    def stories(self) -> tuple[str, ...]:
        if "stories" not in self._cache:
            self._cache["stories"] = self._stories()
        return self._cache["stories"]

    # --- work facts -----------------------------------------------------------------------

    def _work(self, fact: str) -> bool:
        match fact:
            case "setup_ready":
                return _setup_ready(self.repo)
            case "methods_applied":
                from harness.elicitation_store import methods_complete

                return methods_complete(self.repo, self.session.id)
            case "methods_selected":
                from harness.elicitation_store import methods_selected

                return methods_selected(self.repo, self.session.id)
            case "entry_tracked":
                return bool(self.session.entry_item)
            case "entry_refined_now":
                entry = self.entry()
                return entry is not None and isinstance(refined.check(entry), Ok)
            case "entry_is_parent":
                entry = self.entry()
                return entry is not None and entry.kind in PARENT_KINDS
            case "any_published":
                from harness.workflow_evidence import publications

                return bool(publications(self.session))
            case "published_after_approach":
                from harness.workflow_evidence import (
                    history,
                    item_digest,
                    latest_approach,
                    option_id,
                    publications,
                )

                approach = latest_approach(self.session)
                approval = next(
                    (
                        entry
                        for entry in reversed(history(self.session))
                        if entry.get("gate") == "publish-items"
                        and entry.get("status") == "answered"
                        and option_id(entry) == "approve"
                    ),
                    {},
                )
                receipts = tuple(
                    receipt
                    for receipt in publications(self.session)
                    if receipt.get("approach_id") == approach
                    and receipt.get("approval_id")
                    == questions.approval_id(approval.get("id", ""))
                )
                approved = (approval.get("binds") or {}).get("values", {})
                expected_items = tuple(
                    part.strip()
                    for part in approved.get("items", "").split(",")
                    if part.strip()
                )
                expected = int(approved.get("count", 0))
                matched = tuple(
                    receipt
                    for token in expected_items
                    for receipt in receipts
                    if token
                    in (
                        f"key:{receipt.get('item', '')}",
                        f"title:{receipt.get('title', '')}",
                    )
                )
                return bool(
                    approach
                    and expected > 0
                    and len(expected_items) == expected
                    and len(matched) == expected
                    and len({receipt.get("item") for receipt in matched}) == expected
                    and all(
                        item_digest(self.item(receipt["item"]))
                        == receipt.get("source_digest")
                        for receipt in matched
                    )
                )
            case "approach_drafted":
                return self._approach_drafted()
            case "stories_exist":
                return bool(self.stories())
            case "entry_done":
                entry = self.entry()
                return entry is not None and entry.state == LogicalState.DONE
            case _:
                raise KeyError(f"no reader for the work fact {fact!r}")

    def _approach_drafted(self) -> bool:
        if self.session.entry_item:
            match documents.document_path(
                self.repo, self.ops(), self.session.entry_item, "approach"
            ):
                case Ok(path):
                    return path.is_file()
                case Err():
                    return False
        folder = local_artifacts.artifacts_dir(self.repo)
        if folder is None or not folder.is_dir():
            return False
        started = _timestamp(self.session.created_at)
        return any(
            path.stat().st_mtime >= started for path in folder.rglob("approach-*.md")
        )

    # --- Story facts ----------------------------------------------------------------------

    def _story(self, fact: str, story: str) -> bool:
        if fact == "work_item_linked":
            return self.session.work_item.upper() == story.upper()
        if fact not in workflow_requirements.CHECKS:
            raise KeyError(f"no reader for the Story fact {fact!r}")
        context = workflow_requirements.context(
            self.repo, self.session, story, self.ops()
        )
        try:
            return context.check((fact,))[fact] is None
        except workflow_requirements.UnreachableTracker as exc:
            raise Unreachable(str(exc)) from exc

    # --- reads ----------------------------------------------------------------------------

    def ops(self) -> TrackerOps:
        if "ops" not in self._cache:
            match registry.open_selected(self.repo, settings.load(self.repo)):
                case Ok(ops):
                    self._cache["ops"] = ops
                case Err(failure):
                    raise Unreachable(failure.message)
        return self._cache["ops"]

    def item(self, key: str) -> WorkItem:
        cache = ("item", key.upper())
        if cache not in self._cache:
            match self.ops().get_work_item(key):
                case Ok(found):
                    self._cache[cache] = found
                case Err(failure):
                    raise Unreachable(
                        f"the tracker could not read {key}: {failure.message}"
                    )
        return self._cache[cache]

    def entry(self) -> WorkItem | None:
        return self.item(self.session.entry_item) if self.session.entry_item else None

    def children(self, key: str) -> tuple[WorkItem, ...]:
        match self.ops().list_children(key):
            case Ok(found):
                return found
            case Err(failure):
                raise Unreachable(
                    f"the tracker could not list {key}'s children: {failure.message}"
                )

    def _stories(self) -> tuple[str, ...]:
        entry = self.entry()
        if entry is None:
            return ()
        if entry.kind in BUILDABLE_KINDS:
            return (entry.key,)
        found: list[str] = []
        for child in self.children(entry.id):
            if child.kind in BUILDABLE_KINDS:
                found.append(child.key)
            elif child.kind is WorkItemKind.FEATURE:
                found += [
                    grandchild.key
                    for grandchild in self.children(child.id)
                    if grandchild.kind in BUILDABLE_KINDS
                ]
        return tuple(found)

    def answers(self) -> dict[str, str]:
        """Each question's last answer in this work session, as an option id ("" for typed text)."""
        if "answers" not in self._cache:
            self._cache["answers"] = {
                gate: option for gate, option in _answered(self.repo, self.session)
            }
        return self._cache["answers"]

    def _approvals(self) -> list[str]:
        """The questions answered with an approval, oldest first (the approach, published items)."""
        return [
            gate
            for gate, option in _answered(self.repo, self.session)
            if option in _APPROVED.get(gate, ())
        ]


def _answered(repo: Path, session: work_sessions.Session) -> list[tuple[str, str]]:
    from harness.workflow_evidence import history

    labels = _option_labels()
    found: list[tuple[str, str]] = []
    for entry in history(session):
        from harness.workflow_evidence import referenced

        entry = referenced(repo, session, entry)
        gate = str(entry.get("gate") or "")
        if not gate or entry.get("status") != "answered":
            continue
        answer = questions.choice_label(str(entry.get("answer", ""))).strip().casefold()
        found.append((gate, labels.get(gate, {}).get(answer, "")))
    return found


def _option_labels() -> dict[str, dict[str, str]]:
    match gates.load():
        case Ok((_, catalog)):
            return {
                gate.id: {
                    label.strip().casefold(): option.id
                    for option in gate.options
                    for label in option.label.values()
                }
                for gate in catalog.values()
            }
        case _:
            return {}


def _setup_ready(repo: Path) -> bool:
    match setup.onboarding_status(repo):
        case Ok({"status": "ready", "bmad_ready": True}):
            return True
        case _:
            return False


def _timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


# --- harness next --------------------------------------------------------------------------------


def next_for(repo: Path, session_id: str | None = None) -> Result[dict[str, Any]]:
    """The one next step for the work session, as the agent is told it."""
    repo = repo.resolve()
    chosen = session_id or work_sessions.current(repo)
    if not _setup_ready(repo):
        return bind(route.load(), lambda loaded: Ok(_setup_payload(loaded)))
    if chosen is None:
        return Ok(
            {
                "state": "no_session",
                "say": "No work session is open. Run `harness begin --request \"<the user's "
                'exact request>" --repo <project>`.',
            }
        )
    return bind(
        work_sessions.require_active(repo, chosen),
        lambda session: bind(route.load(), lambda loaded: _next(repo, session, loaded)),
    )


def _setup_payload(loaded: route.Route) -> dict[str, Any]:
    return _payload(loaded, route.Next("step", loaded.step("setup")), None, None)


def _next(
    repo: Path, session: work_sessions.Session, loaded: route.Route
) -> Result[dict[str, Any]]:
    pending = decisions.pending(repo, session.id)
    if pending is not None and decisions.is_blocking(
        decisions.record(repo, pending.scope) or {}
    ):
        return Ok(
            {
                "state": "waiting_for_human",
                "session_id": session.id,
                "question": pending.question,
                "options": list(pending.options),
                "say": "The user has not answered this question yet. If they replied in chat, "
                "their reply is recorded with the next prompt; otherwise show it again with "
                "`harness decision fallback`.",
            }
        )
    facts = ProjectFacts(repo, session)
    try:
        found = route.next_step(loaded, facts)
    except Unreachable as exc:
        return err(
            "tracker_unreachable",
            f"the next step depends on the tracker, and it gave no answer: {exc}. "
            "Recover/reload the owning workflow-integrations gateway before another bounded read; "
            "do not start another provider or replay an uncertain write.",
        )
    return Ok(_payload(loaded, found, session, facts))


def _payload(
    loaded: route.Route,
    found: route.Next,
    session: work_sessions.Session | None,
    facts: ProjectFacts | None,
) -> dict[str, Any]:
    base: dict[str, Any] = {"session_id": session.id if session else None}
    if found.step is None:
        return {
            **base,
            "state": "complete",
            "say": "Every step of the route is done. Mark the workflow complete.",
        }
    step = found.step
    entry = session.entry_item if session else ""
    work_item = found.story or entry or None
    payload = {
        **base,
        "state": found.state,
        "stage": step.stage,
        "step": step.id,
        "work_item": work_item,
        "skill": step.skill or None,
        "gate": step.gate or None,
        "command": route.substitute(
            step.command, (("story", found.story or ""), ("entry", entry))
        )
        or None,
        "say": step.say or _default_say(step),
        "missing": [
            {
                "fact": name,
                "description": loaded.facts[name].description,
                "how": loaded.facts[name].how,
            }
            for name in dict.fromkeys(
                check
                for fact in found.missing
                for check in (
                    route.failing_checks(loaded, facts, fact, found.story)
                    if facts is not None
                    else (fact,)
                )
            )
            if loaded.facts[name].kind == "check"
        ],
    }
    return payload


def _default_say(step: route.Step) -> str:
    parts = []
    if step.skill:
        parts.append(f"Run the {step.skill} skill as it is written")
    if step.command:
        parts.append("use the command for the path or record it needs")
    if step.gate:
        parts.append(f"end with `harness decision present --gate {step.gate}`")
    return "; ".join(parts) + "." if parts else ""


def next_stage(repo: Path, session_id: str | None) -> str | None:
    """The stage the work session is in, as the route gives it; None when it cannot be known."""
    match next_for(repo, session_id):
        case Ok({"stage": str() as stage}):
            return stage
        case _:
            return None
