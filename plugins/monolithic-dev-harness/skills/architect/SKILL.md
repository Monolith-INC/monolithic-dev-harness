---
name: architect
description: "Sketch types, signatures, and module structure before code for a harness Task or Story, then implement against the sketch. Use from implement-story for any Task that adds or reshapes an interface, or on 'architect this' / 'design this' where jumping to code would lock in the wrong shape."
---

# Architect

Design before implementing. Sketch types, function signatures, class shapes, and module boundaries
with `not implemented` bodies and pseudocode, compare at least two structurally different sketches,
then fill in code against the chosen one. If implementation proves the sketch wrong, scrap it and
redesign.

Adapted from pstack's `architect` (MIT, Lauren Tan). The multi-model arena becomes two independent
design subagents on the same host.

## Inputs

- The Task (or Story) and its acceptance criteria from the backlog stage.
- The technical specification from `write-spec`. The spec owns the *how*; this skill turns it into
  code shapes and never contradicts it silently. A needed contradiction goes back to the spec.
- Any `ARCHITECTURE-SPINE.md`, `DESIGN.md`, and `EXPERIENCE.md` adopted by the product spec. Their
  `AD-N`, token, journey, and interaction decisions are binding. This Task-level skill fills in code
  shape inside them; it never reopens or overrides them.

## Phase A: Ground

Build a real mental model of every system the new code touches. Follow the repository's routing
(`AGENTS.md` → the subproject router → the documents it names) instead of exploring at random. Read
the existing code the change will sit next to, and name the conventions it must follow (state
management, layer boundaries, error types, naming, localization, design tokens).

Map each inherited `AD-N` that applies to the Task. If the existing code contradicts the spine,
surface the conflict before sketching; do not silently choose one source of truth.

Skip grounding only for genuinely greenfield code with nothing around it.

## Phase B: Sketch twice

Produce **at least two structurally distinct candidates**: whole-shape alternatives, not point fixes
inside one shape. Run them as two parallel design subagents with the same grounding (Claude Code:
the Agent tool; Cursor: the Task tool). Give each `references/runner-prompt.md` as its prompt. Each
candidate returns a design package shaped per `references/rationale-template.md`: the caller's usage
first, then the type sketch, signatures, module map, and rationale.

Screen every candidate against [`references/design-red-flags.md`](references/design-red-flags.md).
Reject or revise shallow modules, information leakage, temporal decomposition, and pass-through
methods. Prefer the design that hides more complexity behind a smaller public surface.

Synthesize one design and record the decision in the rationale's "Synthesis decision" section.

## Phase C: Agree

Inside `implement-story`, the plan was already approved at gate G2, so proceed without another
checkpoint unless the sketch changes a public contract the spec did not anticipate. In that case,
stop and show the user the delta before writing code.

## Phase D: Implement against the sketch

Replace `not implemented` bodies with code. The sketch is the contract. A needed parameter, type,
or dependency the sketch did not anticipate is a signal: decide whether the sketch was wrong, the
requirement was missed, or the implementation is overreaching, and say which.

## Phase E: Scrap when the architecture is wrong

The trigger is repeated friction of the same shape, not one hard case: the same workaround in
unrelated places, special-case branches piling up, escape-hatch types, callers needing to know the
abstraction's internals, or two or more Phase D deviations of the same shape. When you scrap,
re-ground on what was built, redesign as if the new constraints were day-one assumptions, subtract
before adding, and return to Phase B.

## Outputs

The usage sketch and type sketch (one file for small changes; module map plus types for larger
ones) and the rationale per `references/rationale-template.md`, attached to the Task's evidence.
