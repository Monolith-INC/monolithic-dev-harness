---
id: "3-mechanics/contracts"
tier: 3
type: "mechanics"
area: "contracts"
title: "Configuration and provider contracts"
read_when: "Finding the canonical shape of settings, tracker data and gateway operations."
provenance: "derived"
sources:
  - "plugins/monolithic-dev-harness/config/settings.schema.json"
  - "plugins/monolithic-dev-harness/scripts/integrations/contracts.py"
  - "plugins/monolithic-dev-harness/config/mode.schema.json"
  - "plugins/monolithic-dev-harness/.mcp.json"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[2-structure/architecture]]"
---

## Summary

Settings, modes and provider interfaces have source-owned schemas or typed contracts.

## Commands

Read config/settings.schema.json, config/mode.schema.json and scripts/integrations/contracts.py inside the plugin before changing their consumers.

## Detail

The configured tracker and source-control provider are selected in project settings. Provider declarations belong to tracker folders. Review-toolkit connections are a separate configuration: the owner selected Linear project P-AGE-5 for reviews; this setup does not silently rewrite the harness project tracker settings.

## Open questions

- Existing local work-item identifiers are not automatically Linear issue identifiers.
