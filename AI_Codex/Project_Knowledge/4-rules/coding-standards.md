---
id: "4-rules/coding-standards"
tier: 4
type: "rules"
area: "coding"
title: "Coding and dependency rules"
read_when: "Checking source conventions and prohibited implementation shortcuts."
provenance: "stated"
sources:
  - "CONSTITUTION.md"
  - "docs/03-engineering/coding-standards.md"
  - "AGENTS.md"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[4-rules/functional-principles]]"
---

## Summary

Prefer explicit, predictable transformations and keep each concern at its owner boundary.

## Mandated

The engineering guide requires Ruff-clean Python 3.12 code, timezone-aware datetimes, subprocess timeouts, short actionable refusals and shell scripts with set -euo pipefail. Rules return decisions rather than raising for expected conditions. Constitution Article 14 keeps provider-specific work in the provider or its adapter.

## Prohibited

No third-party dependency in a hook or installer path. No broad unexplained noqa. Constitution Article 11 requires removal of the replaced implementation rather than compatibility paths or obsolete parallel mechanisms.

## Enforcement

Ruff configuration, ShellCheck, repository checks, hook tests and review.

## Open questions

- Source documents can lag the runtime; disagreements should be reported rather than silently resolved by invention.
