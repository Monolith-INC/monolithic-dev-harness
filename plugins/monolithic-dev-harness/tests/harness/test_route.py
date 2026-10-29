"""The workflow route has no dead ends.

The route walk starts from every kind of starting point, answers every question every way, and
does each step the route names. From every state it reaches it checks that:

- the route names a step, or says the work is complete;
- a guarded action is never named before what its guard requires is done;
- doing a step finishes it (its facts, and what it records alongside, make it done);
- no sequence of approving answers comes back to a state it has been in.

A dead end, a loop or a guard asking for something the route produces later fails here, not in a
live trial. The 8082 replay is the starting point of the 2026-10-16 live run: a draft Story with no
acceptance criteria, before setup.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from harness import gates, route, route_facts

ROUTE = route.load_or_raise()
_, GATES = gates.load().value
TYPED = ""  # an answer typed in chat that is none of the options


@dataclass(frozen=True)
class Start:
    name: str
    tracked: bool
    refined: bool
    parent: bool
    setup: bool = True


STARTS = (
    Start("request without an item", tracked=False, refined=False, parent=False),
    Start(
        "request before setup", tracked=False, refined=False, parent=False, setup=False
    ),
    Start("draft Story", tracked=True, refined=False, parent=False),
    Start("refined Story", tracked=True, refined=True, parent=False),
    Start("draft Feature", tracked=True, refined=False, parent=True),
    Start("refined Feature", tracked=True, refined=True, parent=True),
)


class World(route.Recorded):
    """Facts as the project would hold them; the starting item's Stories appear once split."""

    def __init__(self, start: Start) -> None:
        work = {"setup_ready"} if start.setup else set()
        if start.tracked:
            work.add("entry_tracked")
        if start.refined:
            work.add("entry_refined_now")
        if start.parent:
            work.add("entry_is_parent")
        super().__init__(work=work)
        self.parent = start.parent

    def stories(self) -> tuple[str, ...]:
        if "entry_tracked" not in self.work:
            return ()
        if self.parent:
            return ("S1", "S2") if "stories_exist" in self.work else ()
        return ("E",)

    def check(self, fact: str, story: str | None) -> bool:
        assert (story is None) == (fact in route_facts.WORK_FACTS), (fact, story)
        if story == "E" and fact == "story_refined":
            return "entry_refined_now" in self.work  # the same tracker item
        return super().check(fact, story)

    def key(self) -> tuple:
        return (
            frozenset(self.work),
            frozenset((s, frozenset(f)) for s, f in self.per_story.items()),
            frozenset(self.answers.items()),
        )

    def copy(self) -> World:
        twin = World.__new__(World)
        route.Recorded.__init__(
            twin,
            work=set(self.work),
            per_story={s: set(f) for s, f in self.per_story.items()},
            answers=dict(self.answers),
        )
        twin.parent = self.parent
        return twin


def _record(world: World, facts: tuple[str, ...], story: str | None) -> None:
    for name in facts:
        fact = ROUTE.facts[name]
        if fact.kind != "check":
            continue
        if name in route_facts.WORK_FACTS:
            world.work.add(name)
        else:
            world.per_story.setdefault(story or "", set()).add(name)


def moves(world: World, found: route.Next) -> list[tuple[World, bool]]:
    """Each way the step can be done: (resulting world, whether that way approves)."""
    step = found.step
    assert step is not None
    results: list[tuple[World, bool]] = []
    asks_answer = step.gate and any(
        _depends_on_answer(name, step.gate) for name in step.done
    )
    if asks_answer:
        for option in (*(o.id for o in GATES[step.gate].options), TYPED):
            after = world.copy()
            after.answers[step.gate] = option
            done = not route.missing(ROUTE, after, step, found.story)
            results.append((after, done))
        # The starting item can also be tracked instead of asking.
        if step.id == "starting-item":
            after = world.copy()
            after.work.add("entry_tracked")
            results.append((after, True))
        return results
    after = world.copy()
    _record(after, (*step.done, *step.also), found.story)
    if step.id == "split":
        after.work.add("stories_exist")
    results.append((after, True))
    return results


def _guards_hit(step: route.Step) -> tuple[str, ...]:
    """The guarded actions a step performs: those whose guarded step produces any of the same
    facts (moving the Story to in progress, creating Tasks, changing code, marking it done)."""
    return tuple(
        guard
        for guard in route.guards(ROUTE)
        if set(next(s for s in ROUTE.steps if s.guard == guard).done) & set(step.done)
    )


def _depends_on_answer(name: str, gate: str) -> bool:
    """Whether the fact is decided by the answer to `gate`."""
    fact = ROUTE.facts[name]
    if fact.kind == "answer":
        return fact.gate == gate
    return any(_depends_on_answer(part, gate) for part in fact.of)


def walk(start: Start) -> tuple[int, list[str]]:
    """Every state reachable from `start`; returns how many and the problems found."""
    problems: list[str] = []
    seen: set[tuple] = set()
    first = World(start)
    stack: list[tuple[World, tuple[tuple, ...]]] = [(first, ())]
    while stack:
        world, approving_path = stack.pop()
        found = route.next_step(ROUTE, world)
        if found.state == "complete":
            continue
        step = found.step
        assert step is not None
        where = f"{start.name}: {step.id} for {found.story}"
        if not found.missing:
            problems.append(f"{where}: named a step that is already done")
        for guard in _guards_hit(step):
            lacking = [
                r.id
                for r in route.guard_requirements(ROUTE, guard)
                if not world.check(r.id, found.story)
            ]
            if lacking:
                problems.append(
                    f"{where}: guard {guard} would refuse it, lacking {lacking}"
                )
        state = world.key()
        if state in approving_path:
            problems.append(f"{where}: approving answers came back to the same state")
            continue
        ways = moves(world, found)
        if not any(approves for _, approves in ways):
            problems.append(f"{where}: no answer or action finishes the step")
        for after, approves in ways:
            if approves and route.missing(ROUTE, after, step, found.story):
                problems.append(f"{where}: doing the step did not finish it")
                continue
            if after.key() in seen and not approves:
                continue
            seen.add(after.key())
            stack.append((after, (*approving_path, state) if approves else ()))
    return len(seen), problems


@pytest.mark.parametrize("start", STARTS, ids=[s.name for s in STARTS])
def test_every_reachable_state_has_a_way_forward(start: Start) -> None:
    reached, problems = walk(start)
    assert reached > 10
    assert problems == []


def _approving(world: World, found: route.Next) -> World:
    """The answer a user who agrees gives: the recommended option, or approve."""
    step = found.step
    assert step is not None
    if step.id == "starting-item":
        after = world.copy()
        after.work.add("entry_tracked")
        return after
    options = [(after, done) for after, done in moves(world, found) if done]
    gate = GATES.get(step.gate) if step.gate else None
    if gate is not None and any(_depends_on_answer(n, gate.id) for n in step.done):
        wanted = gate.recommended or gate.options[0].id
        for after, _ in options:
            if after.answers.get(step.gate) == wanted:
                return after
    return options[0][0]


def replay(start: Start) -> list[str]:
    world = World(start)
    steps: list[str] = []
    for _ in range(200):
        found = route.next_step(ROUTE, world)
        if found.state == "complete":
            return steps
        assert found.step is not None
        steps.append(found.step.id)
        world = _approving(world, found)
    raise AssertionError(f"no end after {steps}")


def test_the_8082_run_goes_through_every_stage_in_order() -> None:
    """A draft Story before setup, named by a tracker link (the 2026-10-16 live run)."""
    start = Start("8082", tracked=False, refined=False, parent=False, setup=False)
    assert replay(start) == [
        "setup",
        "starting-item",
        "discovery",
        "planning-methods",
        "method-application",
        "approach",
        "hardening",
        "refine-entry",
        "story-plan",
        "story-tasks",
        "risk",
        "verification-plan",
        "manifest",
        "start",
        "implement",
        "review",
        "resolve",
        "story-done",
    ]


def test_a_refined_story_used_as_it_is_skips_discovery() -> None:
    world = World(Start("refined", tracked=True, refined=True, parent=False))
    found = route.next_step(ROUTE, world)
    assert found.step is not None and found.step.id == "refined-start"
    world.answers["refined-start"] = "as-is"
    found = route.next_step(ROUTE, world)
    assert found.step is not None and found.step.id == "story-plan"


def test_a_feature_is_split_and_each_story_is_prepared_before_any_is_delivered() -> (
    None
):
    steps = replay(Start("feature", tracked=True, refined=False, parent=True))
    assert steps.index("split") < steps.index("story-refine")
    assert steps.count("story-plan") == 2
    last_preparation = len(steps) - 1 - steps[::-1].index("manifest")
    assert last_preparation < steps.index("start")
    assert steps[-1] == "close-entry"


def test_stopping_at_the_idea_completes_the_work() -> None:
    world = World(Start("idea", tracked=False, refined=False, parent=False))
    world.answers["starting-point"] = "explore"
    assert route.next_step(ROUTE, world).step.id == "idea"  # type: ignore[union-attr]
    world.answers["idea-continue"] = "stop"
    found = route.next_step(ROUTE, world)
    assert found.state == "complete" and found.step is not None


def test_guards_require_only_what_the_route_does_before_them() -> None:
    assert [r.id for r in route.guard_requirements(ROUTE, "tasks-publish")] == [
        "story_refined",
        "plan_approved",
    ]
    code = [r.id for r in route.guard_requirements(ROUTE, "code-change")]
    assert code[-2:] == ["work_item_linked", "work_item_started"]
    assert "code_changed" not in [
        r.id for r in route.guard_requirements(ROUTE, "completion")
    ]


def test_every_check_has_a_reader() -> None:
    every = route_facts.WORK_FACTS | route_facts.STORY_FACTS
    for step in ROUTE.steps:
        names = {*step.done, *step.when, *step.unless}
        checks = {n for n in names if ROUTE.facts[n].kind == "check"}
        readers = (
            route_facts.WORK_FACTS if step.scope == "work" else route_facts.STORY_FACTS
        )
        assert checks <= readers, (step.id, checks - readers)
        assert set(step.also) <= every, step.id
    assert {n for n, f in ROUTE.facts.items() if f.kind == "check"} <= every


def test_a_route_naming_an_unknown_fact_is_refused() -> None:
    from harness import prepared_workflows

    catalog = prepared_workflows.load_catalog()
    catalog["route"][0]["done"] = ["no_such_fact"]
    with pytest.raises(ValueError, match="unknown fact"):
        route.parse(catalog)


def test_story_steps_after_delivery_are_refused() -> None:
    from harness import prepared_workflows

    catalog = prepared_workflows.load_catalog()
    steps = catalog["route"]
    review = next(s for s in steps if s["id"] == "review")
    review["scope"] = "story"
    with pytest.raises(ValueError, match="consecutive"):
        route.parse(catalog)
