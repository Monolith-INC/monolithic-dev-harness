---
id: "4-rules/functional-principles"
tier: 4
type: "rules"
area: "functional"
title: "Owner functional coding discipline"
read_when: "Choosing the shape of new logic or a refactor."
provenance: "stated"
sources: []
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links: []
---

## Summary

The owner-provided project instructions in this setup conversation require functional coding as the main discipline.

## Mandated

Prefer immutable values, algebraic result types, composition pipelines, explicit return values and pattern matching. Research the functional tools and documentation of the language and stack being changed. Keep transformations separate from file, network and other effects.

## Prohibited

Avoid mutable variables when a function can express the same transformation. When a choice is not binary, prefer a switch expression or pattern match.

## Enforcement

These are owner statements from the project instructions supplied in this chat; this unit preserves them as stated requirements. This unit is not automatically derived from an on-disk style file.

## Open questions

- No repository-wide functional-library selection for Python was specified.
