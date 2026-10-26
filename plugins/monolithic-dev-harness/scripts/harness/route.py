"""The workflow route, read from the catalog, and the one next step it gives for a set of facts.

The route (`route` in `config/prepared-workflows.json`) is the only statement of the workflow's
order. Each step names its stage, the source skill that does it, the question that ends it, and the
facts that prove it done. `next_step` walks the route over the facts and returns the first step that
applies and is not done; nothing else decides what comes next. The guards read their requirements
from the same route (`guard_requirements`), so a guard can never ask for something the route
produces later.

Facts come in four kinds:

- `check`   read from the project, the tracker and the harness records (see `route_facts`).
- `answer`  the user's last answer to a question in this work session, among `options` (any, when
            omitted).
- `any`, `all`, `not`  built from other facts.

This module is pure: it takes a `Facts` reader and never touches the disk beyond loading the
catalog.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from core.result import Err, Ok, Result, attempt
from harness import gates as gate_catalog

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCOPES = ("work", "story", "delivery")
STAGES = (
    "setup",
    "ideate",
    "discovery",
    "planning",
    "hardening",
    "refinement",
    "preparation",
    "execution",
    "verify",
)
KINDS = ("check", "answer", "any", "all", "not")


class _Invalid(ValueError):
    """The route or its facts cannot be used as written."""


@dataclass(frozen=True)
class Fact:
    id: str
    kind: str
    description: str = ""
    how: str = ""
    guard: bool = True  # a check the guards may require; False for progress-only facts
    gate: str = ""
    options: tuple[str, ...] = ()  # answer: the options that make it hold; () means any
    of: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    id: str
    stage: str
    scope: str
    done: tuple[str, ...]
    when: tuple[str, ...] = ()
    unless: tuple[str, ...] = ()
    skill: str = ""
    gate: str = ""
    command: str = ""
    say: str = ""
    guard: str = ""
    end: bool = False
    also: tuple[str, ...] = ()


@dataclass(frozen=True)
class Route:
    facts: dict[str, Fact]
    steps: tuple[Step, ...]

    def step(self, step_id: str) -> Step:
        return next(step for step in self.steps if step.id == step_id)

    @property
    def stages(self) -> tuple[str, ...]:
        """The stages in route order, each once."""
        return tuple(dict.fromkeys(step.stage for step in self.steps))


class Facts(Protocol):
    """What `next_step` reads. `story` is None for facts about the work as a whole."""

    def check(self, fact: str, story: str | None) -> bool: ...

    def answer(self, gate: str) -> str | None: ...

    def stories(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class Next:
    """The one next step, or the end of the route."""

    state: str  # "step" or "complete"
    step: Step | None = None
    story: str | None = None
    missing: tuple[str, ...] = ()  # the step's done facts that do not hold yet


# --- loading -------------------------------------------------------------------------------------


def load(plugin_root: Path = PLUGIN_ROOT) -> Result[Route]:
    return attempt(
        lambda: _load(plugin_root), "route_invalid", "workflow route", _Invalid
    )


def load_or_raise(plugin_root: Path = PLUGIN_ROOT) -> Route:
    return _load(plugin_root)


def _load(plugin_root: Path) -> Route:
    from harness import prepared_workflows

    try:
        catalog = prepared_workflows.load_catalog(plugin_root)
    except ValueError as exc:
        raise _Invalid(str(exc)) from exc
    return parse(catalog, plugin_root)


def parse(catalog: dict[str, Any], plugin_root: Path = PLUGIN_ROOT) -> Route:
    raw_facts = catalog.get("facts")
    raw_steps = catalog.get("route")
    if (
        not isinstance(raw_facts, dict)
        or not isinstance(raw_steps, list)
        or not raw_steps
    ):
        raise _Invalid("the catalog needs `facts` and a non-empty `route`")
    facts = {name: _fact(name, entry) for name, entry in raw_facts.items()}
    steps = tuple(_step(entry) for entry in raw_steps)
    _check(facts, steps, plugin_root)
    return Route(facts, steps)


def _strings(value: Any, what: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise _Invalid(f"{what} must be a list of names")
    return tuple(value)


def _fact(name: str, entry: Any) -> Fact:
    if not isinstance(entry, dict) or entry.get("kind") not in KINDS:
        raise _Invalid(f"fact {name!r} needs a kind among {KINDS}")
    kind = entry["kind"]
    fact = Fact(
        id=name,
        kind=kind,
        description=str(entry.get("description", "")),
        how=str(entry.get("how", "")),
        guard=entry.get("guard", True) is not False,
        gate=str(entry.get("gate", "")),
        options=_strings(entry.get("options"), f"fact {name!r} options"),
        of=_strings(entry.get("of"), f"fact {name!r} of"),
    )
    match kind:
        case "check" if not (fact.description.strip() and fact.how.strip()):
            raise _Invalid(f"check fact {name!r} needs a description and how")
        case "answer" if not fact.gate:
            raise _Invalid(f"answer fact {name!r} needs a gate")
        case "any" | "all" if not fact.of:
            raise _Invalid(f"fact {name!r} combines nothing")
        case "not" if len(fact.of) != 1:
            raise _Invalid(f"fact {name!r} negates exactly one fact")
    return fact


def _step(entry: Any) -> Step:
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        raise _Invalid("every route step needs an id")
    name = entry["id"]
    return Step(
        id=name,
        stage=str(entry.get("stage", "")),
        scope=str(entry.get("scope", "")),
        done=_strings(entry.get("done"), f"step {name!r} done"),
        when=_strings(entry.get("when"), f"step {name!r} when"),
        unless=_strings(entry.get("unless"), f"step {name!r} unless"),
        skill=str(entry.get("skill", "")),
        gate=str(entry.get("gate", "")),
        command=str(entry.get("command", "")),
        say=str(entry.get("say", "")),
        guard=str(entry.get("guard", "")),
        end=entry.get("end") is True,
        also=_strings(entry.get("also"), f"step {name!r} also"),
    )


def _check(facts: dict[str, Fact], steps: tuple[Step, ...], plugin_root: Path) -> None:
    match gate_catalog.load(plugin_root / "config" / "gates.toml"):
        case Ok((_, gates)):
            pass
        case Err(failure):
            raise _Invalid(f"the question catalog cannot be read: {failure.message}")
    for fact in facts.values():
        for part in fact.of:
            if part not in facts:
                raise _Invalid(f"fact {fact.id!r} names an unknown fact {part!r}")
        if fact.kind == "answer":
            gate = gates.get(fact.gate)
            if gate is None:
                raise _Invalid(
                    f"fact {fact.id!r} names an unknown question {fact.gate!r}"
                )
            unknown = set(fact.options) - {option.id for option in gate.options}
            if unknown:
                raise _Invalid(
                    f"fact {fact.id!r} names options {sorted(unknown)} not in {gate.id}"
                )
    _acyclic(facts)
    seen: set[str] = set()
    guards: set[str] = set()
    for step in steps:
        if step.id in seen:
            raise _Invalid(f"route step {step.id!r} appears twice")
        seen.add(step.id)
        if step.stage not in STAGES or step.scope not in SCOPES:
            raise _Invalid(f"route step {step.id!r} has an unknown stage or scope")
        if not step.done and not step.end:
            raise _Invalid(f"route step {step.id!r} has no fact that proves it done")
        for name in (*step.done, *step.when, *step.unless, *step.also):
            if name not in facts:
                raise _Invalid(f"route step {step.id!r} names an unknown fact {name!r}")
        for name in step.also:
            if facts[name].kind != "check":
                raise _Invalid(f"route step {step.id!r}: `also` lists checks only")
        if step.scope != "work":
            for name in step.done:
                if facts[name].kind != "check":
                    raise _Invalid(f"Story step {step.id!r} is done by checks only")
        if step.gate and step.gate not in gates:
            raise _Invalid(
                f"route step {step.id!r} asks an unknown question {step.gate!r}"
            )
        if (
            step.skill
            and not (plugin_root / "skills" / step.skill / "SKILL.md").is_file()
        ):
            raise _Invalid(
                f"route step {step.id!r} names a missing skill {step.skill!r}"
            )
        if step.guard:
            if step.guard in guards:
                raise _Invalid(f"guard {step.guard!r} belongs to two steps")
            guards.add(step.guard)
    scopes = [step.scope for step in steps]
    if "delivery" in scopes:
        first = scopes.index("delivery")
        last = len(scopes) - scopes[::-1].index("delivery")
        if any(scope != "delivery" for scope in scopes[first:last]):
            raise _Invalid("the delivery steps must be consecutive")


def _acyclic(facts: dict[str, Fact]) -> None:
    def visit(name: str, trail: tuple[str, ...]) -> None:
        if name in trail:
            raise _Invalid(
                f"facts refer to each other in a circle: {' -> '.join(trail)}"
            )
        for part in facts[name].of:
            visit(part, (*trail, name))

    for name in facts:
        visit(name, ())


# --- evaluation ----------------------------------------------------------------------------------


def holds(route: Route, facts: Facts, name: str, story: str | None = None) -> bool:
    fact = route.facts[name]
    match fact.kind:
        case "check":
            return facts.check(name, story)
        case "answer":
            answer = facts.answer(fact.gate)
            return answer is not None and (not fact.options or answer in fact.options)
        case "any":
            return any(holds(route, facts, part, story) for part in fact.of)
        case "all":
            return all(holds(route, facts, part, story) for part in fact.of)
        case _:
            return not holds(route, facts, fact.of[0], story)


def applies(route: Route, facts: Facts, step: Step, story: str | None = None) -> bool:
    return all(holds(route, facts, name, story) for name in step.when) and not any(
        holds(route, facts, name, story) for name in step.unless
    )


def missing(
    route: Route, facts: Facts, step: Step, story: str | None = None
) -> tuple[str, ...]:
    return tuple(name for name in step.done if not holds(route, facts, name, story))


def failing_checks(
    route: Route, facts: Facts, name: str, story: str | None = None
) -> tuple[str, ...]:
    """The checks under a fact that do not hold, so the agent is told what to make true."""
    if holds(route, facts, name, story):
        return ()
    fact = route.facts[name]
    match fact.kind:
        case "check":
            return (name,)
        case "any" | "all":
            found = (
                part
                for child in fact.of
                for part in failing_checks(route, facts, child, story)
            )
            return tuple(dict.fromkeys(found))
        case _:
            return ()


def next_step(route: Route, facts: Facts) -> Next:
    """The first step that applies and is not done, in route order.

    Work steps are checked once; Story steps for each Story in turn (all Stories are refined and
    prepared before any is delivered); delivery steps Story by Story, each Story delivered before
    the next one starts.
    """
    delivered = False
    for step in route.steps:
        match step.scope:
            case "work":
                found = _visit(route, facts, step, None)
                if found is not None:
                    return found
            case "story":
                for story in facts.stories():
                    found = _visit(route, facts, step, story)
                    if found is not None:
                        return found
            case _ if not delivered:
                delivered = True
                chain = [s for s in route.steps if s.scope == "delivery"]
                for story in facts.stories():
                    for each in chain:
                        found = _visit(route, facts, each, story)
                        if found is not None:
                            return found
    return Next("complete")


def _visit(route: Route, facts: Facts, step: Step, story: str | None) -> Next | None:
    if not applies(route, facts, step, story):
        return None
    if step.end:
        return Next("complete", step, story)
    lacking = missing(route, facts, step, story)
    return Next("step", step, story, lacking) if lacking else None


# --- what the guards require ---------------------------------------------------------------------


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str
    how: str
    stage: str  # where the route produces it
    skill: str


def guard_requirements(route: Route, guard: str) -> tuple[Requirement, ...]:
    """What must hold for a Story before the guarded action: the done facts of every Story and
    delivery step before the step that performs it, in route order."""
    chain = [s for s in route.steps if s.scope == "story"] + [
        s for s in route.steps if s.scope == "delivery"
    ]
    owner = next((i for i, s in enumerate(chain) if s.guard == guard), None)
    if owner is None:
        raise _Invalid(f"no route step performs the guarded action {guard!r}")
    found: dict[str, Requirement] = {}
    for step in chain[:owner]:
        for name in step.done:
            fact = route.facts[name]
            if fact.guard and name not in found:
                found[name] = Requirement(
                    name,
                    fact.description,
                    fact.how,
                    step.stage,
                    step.skill or "harness",
                )
    return tuple(found.values())


def guards(route: Route) -> tuple[str, ...]:
    return tuple(step.guard for step in route.steps if step.guard)


# --- helpers for tests and tools -----------------------------------------------------------------


@dataclass
class Recorded:
    """Facts kept in memory: for tests and for the route walk."""

    work: set[str] = field(default_factory=set)
    per_story: dict[str, set[str]] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    story_keys: tuple[str, ...] = ()
    reads: Callable[[str, str | None], None] | None = None

    def check(self, fact: str, story: str | None) -> bool:
        if self.reads is not None:
            self.reads(fact, story)
        if story is None:
            return fact in self.work
        return fact in self.per_story.get(story, set())

    def answer(self, gate: str) -> str | None:
        return self.answers.get(gate)

    def stories(self) -> tuple[str, ...]:
        return self.story_keys


def substitute(command: str, values: Iterable[tuple[str, str]]) -> str:
    for name, value in values:
        if value:
            command = command.replace(f"<{name}>", value)
    return command
