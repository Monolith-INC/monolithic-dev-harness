---
id: "4-rules/runtime-budgets"
tier: 4
type: "rules"
area: "budgets"
title: "Current hook time budgets"
read_when: "Assessing whether hook work can exceed its local time limit."
provenance: "derived"
sources:
  - "plugins/monolithic-dev-harness/scripts/harness/hook_budget.py"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links: []
---

## Summary

The current budget module defines 12 seconds for pre-tool events and 7 seconds for other events.

## Mandated

The helper measures elapsed time from the supplied process-start timestamp. Signal-capable execution can interrupt a handler; other execution paths check between steps.

## Prohibited

Do not infer that the budget can interrupt work after commit(): the module explicitly protects the short local recording section once committed.

## Enforcement

hook_budget.run, check, step and commit, with focused timeout tests.

## Open questions

- No additional numeric latency, throughput or service budget was supplied by the owner.
