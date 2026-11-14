---
id: "2-structure/architecture"
tier: 2
type: "structure"
area: "architecture"
title: "Authority and adapter boundaries"
read_when: "Checking whether a change puts behavior in the component that owns it."
provenance: "stated"
sources:
  - "CONSTITUTION.md"
  - "docs/01-architecture/architecture.md"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[2-structure/decisions]]"
  - "[[4-rules/security-compliance]]"
---

## Summary

Skills guide work; deterministic runtime checks decide whether supported operations may proceed. An adapter owns translation for its provider.

## Layout

The source documents separate skills, orchestration, provider adapters, host adapters, the gateway and the hook runtime.

## Rules

Constitution Articles 13 and 14 require centrally defined messages and one shared interface. Translation belongs in adapters; delivery belongs to the bus; policy belongs to the harness. A status report, cancellation request or operation receipt cannot manufacture approval. Skills and orchestrators cannot grant themselves authority.

## Open questions

- Architecture proposals marked draft or proposed are not established project rules.
