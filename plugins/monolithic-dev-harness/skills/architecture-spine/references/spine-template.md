# Architecture Spine Shape

Remove guidance and empty sections from the finished file. Decisions, not rationale, belong here.

```markdown
---
name: <scope>
type: architecture-spine
purpose: build-substrate | discussion
altitude: initiative | feature | epic
paradigm: <named design pattern>
scope: <what this governs>
status: draft | final
created: YYYY-MM-DD
updated: YYYY-MM-DD
binds: [CAP-N]
sources: []
companions: []
---

# Architecture Spine — <scope>

## Design Paradigm

<Named pattern and how its boundaries map to this system.>

## Inherited Invariants

| Inherited ID | Parent spine | Binds here |
| --- | --- | --- |
| AD-N | <path> | <scope> |

## Invariants and Rules

### AD-1 — <decision>

- **Binds:** <CAP-N, area, or all>
- **Prevents:** <specific cross-unit divergence>
- **Rule:** <enforceable constraint>

## Consistency Conventions

| Concern | Convention |
| --- | --- |
| Naming and public contracts | <rule> |
| IDs, dates, errors, and data formats | <rule> |
| Mutation, logging, configuration, and authorization | <rule> |

## Stack Seed

| Technology | Verified version |
| --- | --- |
| <name> | <version> |

## Structural Seed

<Only cold-start shape that independently built units must share. Prefer valid Mermaid diagrams.>

## Capability to Architecture Map

| Capability | Lives in | Governed by |
| --- | --- | --- |
| CAP-N | <component> | AD-N |

## Deferred

- <decision>: <why it can wait and what reopens it>
```
