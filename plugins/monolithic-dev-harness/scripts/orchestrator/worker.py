from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .adapters import to_anthropic_dialect
from .exhaustive import assert_never
from .failures import HandlerContractError, InputContractError
from .handlers import get_handler
from .invocation import HandlerResult, Invocation
from .manifests import CapabilityManifest, load_skill_instructions
from .schema import validate_inputs
from .state import FrozenDict, Task, TaskState


@dataclass(frozen=True)
class Envelope:
    """Orchestration fields the worker adds to instruction-only results."""

    prompt: str
    attempt: int
    reflection_critiques: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoEnvelope:
    """The handler returned a complete result of its own."""


Envelopes = Envelope | NoEnvelope


@dataclass(frozen=True)
class SkillOutput:
    """One handler run: the work, its reflection state, and what we added.

    Keeping the three apart is what lets the engine evaluate and compare the
    work alone. Flattening them is a presentation step, done once in
    :meth:`to_wire`, so hosts keep receiving the shape they always have.
    """

    product: Mapping[str, Any] = field(default_factory=FrozenDict)
    reflection: Mapping[str, Any] = field(default_factory=FrozenDict)
    envelope: Envelopes = NoEnvelope()

    def to_wire(self) -> dict[str, Any]:
        match self.envelope:
            case NoEnvelope():
                added: dict[str, Any] = {}
            case Envelope(prompt, attempt, critiques):
                added = {
                    "prompt": prompt,
                    "attempt": attempt,
                    **({"reflection_critiques": list(critiques)} if critiques else {}),
                }
            case _ as unmatched:
                assert_never(unmatched)
        reflection = {"reflection": dict(self.reflection)} if self.reflection else {}
        return {**self.product, **reflection, **added}


def execute_skill(
    skill_name: str,
    arguments: dict[str, Any],
    *,
    skills_dir: str,
    manifest: CapabilityManifest,
    task: Task,
) -> SkillOutput:
    """Run a skill handler and return its result for evaluation."""
    input_critiques = validate_inputs(arguments, manifest)
    if input_critiques:
        raise InputContractError("; ".join(input_critiques))

    instructions = load_skill_instructions(skills_dir, skill_name)
    handler = get_handler(skill_name)
    result = handler(
        Invocation(
            arguments=arguments,
            manifest=manifest.wire,
            instructions=instructions,
            attempt=_reflection_attempt(arguments, task),
        )
    )

    if not isinstance(result, HandlerResult):
        raise HandlerContractError(
            f"Handler for '{skill_name}' returned {type(result).__name__}; "
            "handlers must return a HandlerResult."
        )

    return SkillOutput(
        product=result.product,
        reflection=result.reflection,
        envelope=_envelope_for(result.product, instructions, task),
    )


def _envelope_for(
    product: Mapping[str, Any], instructions: str, task: Task
) -> Envelopes:
    if product.get("mode") != "instructions" and "prompt" in product:
        return NoEnvelope()
    return Envelope(
        prompt=to_anthropic_dialect(
            instructions, task.copy_with(state=TaskState.IN_PROGRESS)
        ),
        attempt=task.retry_count + 1,
        reflection_critiques=task.critiques,
    )


def _reflection_attempt(arguments: dict[str, Any], task: Task) -> int:
    """Where this run sits in the reflection sequence.

    A caller resuming a stateless MCP round trip declares its own starting
    attempt; in-process retries advance from there. Both were previously folded
    into ``arguments`` by rewriting the caller's payload on each retry.
    """
    declared = arguments.get("attempt", 0)
    resumed = (
        int(declared)
        if isinstance(declared, (int, float)) and not isinstance(declared, bool)
        else 0
    )
    return resumed + task.retry_count
