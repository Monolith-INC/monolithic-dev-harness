---
id: "3-mechanics/testing"
tier: 3
type: "mechanics"
area: "testing"
title: "Tests and host evidence"
read_when: "Deciding which suite and live evidence a behavior change needs."
provenance: "stated"
sources:
  - "docs/03-engineering/testing.md"
  - "docs/03-engineering/development.md"
  - "plugins/monolithic-dev-harness/tests/run.sh"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[4-rules/workflow]]"
  - "[[5-evolution/risks]]"
---

## Summary

The full runner covers backlog, core, integration, delivery, harness and installer checks. Unit success does not prove hooks fire in a live host.

## Commands

From repository root, use an absolute interpreter so the runner can change directory safely:

```bash
PYTHON="$PWD/.venv/bin/python" plugins/monolithic-dev-harness/tests/run.sh
```

Focused Python suites use the plugin root and scripts/ on PYTHONPATH. tests/settings_fixture.py supplies project settings.

## Detail

The testing guide requires deny and allow cases through the real hook entry point for changed rules, and separate host smoke evidence for live integration. It identifies subprocess host payload tests and installer checks as different boundaries.

## Open questions

- The current test_setup doctor check reads installed host profiles; mixed installed versions can cause a machine-dependent failure.
