# Product Spec Shape

```markdown
---
id: SPEC-<slug>
status: draft | final
companions: [CRITIQUE.md]
sources: []
---

> Canonical product contract. This file and `companions:` are the complete input for backlog,
> technical planning, implementation, and validation. `sources:` are traceability only.

# <Outcome>

## Why

<One paragraph naming the pain, opportunity, vision, or mandate; who is affected; and why now.>

## Capabilities

- **CAP-1**
  - **intent:** <what the user or system can do and the outcome, never implementation>
  - **success:** <testable or demonstrable condition>

## Constraints

- <non-negotiable that rules out at least one design choice>

## Non-goals

- <explicit boundary; at least one>

## Success signal

- <observable world-change that a test or demonstration can decide>

## Assumptions

- <unsupported inference; omit section when empty>

## Open Questions

- <answerable load-bearing gap; omit section when empty>
```

`CRITIQUE.md` records the strongest counterargument, unsupported assumptions, likely failure
cases, a simpler alternative, and the user's response. It is presented with this contract before
backlog handoff.

Other companions are named for their content (`glossary.md`, `failure-modes.md`,
`architecture-diagrams.md`) or retain the upstream owner's name (`DESIGN.md`, `EXPERIENCE.md`,
`ARCHITECTURE-SPINE.md`). Diagrams always live in companions, never in the compact kernel.
