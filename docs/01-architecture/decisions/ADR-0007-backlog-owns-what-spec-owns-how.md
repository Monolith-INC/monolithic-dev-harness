---
title: ADR-0007 Product contract owns intent, backlog owns slices, technical spec owns how
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
---

# ADR-0007: Product contract owns intent, backlog owns slices, technical spec owns the *how*

## Status

Accepted

## Context

The harness now accepts work at three altitudes. Pre-backlog product planning establishes the
initiative or epic intent. The backlog turns that intent into trackable delivery slices. The
delivery stage writes the Story's technical spec. Without explicit ownership, all three can become
competing plans and drift apart.

## Decision

- `product-spec` owns the higher-level intent: Why, stable `CAP-N` capabilities and their success
  conditions, constraints, non-goals, success signal, and adopted UX / architecture companions.
- The backlog owns delivery slicing: Epics, Features, Stories, Story acceptance criteria, points,
  and Tasks. Each slice traces to the capability IDs it covers.
- `write-spec` owns the Story-local *how*: modules, contracts, implementation details, test
  strategy, and risks. It inherits product, UX, and architecture decisions as constraints.

A downstream artifact that needs to change an upstream decision sends the change to its owning
skill. It never changes the decision silently.

## Options Considered

- **Let each stage restate everything:** duplicate, divergent artifacts.
- **Technical spec only:** loses product intent and board-visible delivery slices.
- **Split by altitude and ownership (chosen).**

## Consequences

### Positive

- One source for each decision; product intent, board slices, and technical design remain traceable
  without duplicating ownership.

### Trade-offs

- Product-intent changes return to `product-spec` or its owned companion before re-slicing.
- Scope changes discovered during technical specification still cost a trip back to gate G1.

## Host-specific Impact

None.

## Validation

`skills/product-spec/SKILL.md` → *Handoff*; `skills/write-spec/SKILL.md` → *Harness handoff*;
`skills/architect/SKILL.md` → *Inputs*.

## References

- [../../02-design/workflows.md](../../02-design/workflows.md)
