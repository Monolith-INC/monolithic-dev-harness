---
id: "3-mechanics/runtime-ops"
tier: 3
type: "mechanics"
area: "operations"
title: "Installation and runtime activation"
read_when: "Distinguishing installed files from active host behavior."
provenance: "stated"
sources:
  - "docs/04-operations/deployment.md"
  - "docs/03-engineering/development.md"
  - "install.sh"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[3-mechanics/testing]]"
---

## Summary

The installer owns installed copies and registration. A host restart and hook trust can still be required after installation.

## Commands

Use harness version to inspect the installed command and harness doctor --installations for a bounded installation inventory.

## Detail

Deployment documentation says user and project registrations share one installed package location. Its project installer refuses tracked host configuration rather than silently untracking it. Installed caches are generated files; edit the source checkout and rebuild or reinstall.

## Open questions

- File presence and installation inventory do not establish that a particular tool call receives live governance.
