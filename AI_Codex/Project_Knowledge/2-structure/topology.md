---
id: "2-structure/topology"
tier: 2
type: "structure"
area: "topology"
title: "Repository topology"
read_when: "Locating the authored implementation before reviewing a change."
provenance: "derived"
sources:
  - "README.md"
  - "plugins/monolithic-dev-harness/.mcp.json"
  - "plugins/monolithic-dev-harness/scripts/harness/cli.py"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[3-mechanics/build-tooling]]"
  - "[[2-structure/architecture]]"
---

## Summary

One primary plugin lives under plugins/monolithic-dev-harness, with installer and release tooling at repository root.

## Layout

- scripts/harness/: commands, rules, decisions and mode handling.
- scripts/host_adapters/: host-specific translations.
- scripts/integrations/: provider contracts, gateway and registry.
- runtime/orchestrator_core/: backlog orchestration.
- trackers/: bundled provider folders.
- skills/, agents/, hooks/, config/, modes/: plugin procedures and declarations.
- tests/: backlog, core, integrations, delivery and harness suites.

## Rules

Use authored source paths for changes. Installed plugin caches and release archives are outputs; the build instructions are indexed separately.

## Open questions

- none
