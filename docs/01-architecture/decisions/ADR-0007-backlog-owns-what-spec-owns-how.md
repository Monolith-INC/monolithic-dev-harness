---
title: ADR-0007 Backlog owns the what, the spec owns the how
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# ADR-0007: The backlog stage owns the *what*; the spec owns the *how*

## Status

Accepted

## Context

Two source toolkits each produced a planning artifact: the backlog toolkit's implementation plan
with Tasks, and the delivery toolkit's technical spec. Two plans for one Story drift apart.

## Decision

The backlog stage owns Stories, acceptance criteria, points, and Tasks. `write-spec` takes them as
input and decides only the *how* (architecture, modules, contracts, test strategy, risks). A spec
that would change a Task or a criterion sends the change back to the backlog instead of changing
it silently.

## Options Considered

- **Keep both plans:** duplicate, divergent artifacts.
- **Spec only:** loses the board-visible Tasks the team tracks.
- **Split by responsibility (chosen).**

## Consequences

### Positive

- One source for each fact; the board and the spec cannot disagree about scope.

### Trade-offs

- Scope changes discovered during specification cost a trip back to gate G1.

## Host-specific Impact

None.

## Validation

`skills/write-spec/SKILL.md` → *Harness handoff*; `skills/implement-story/SKILL.md` → inputs table.

## References

- [../../02-design/workflows.md](../../02-design/workflows.md)
