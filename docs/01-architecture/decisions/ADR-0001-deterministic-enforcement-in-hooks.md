---
title: ADR-0001 Deterministic enforcement in hooks
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# ADR-0001: Enforce required behavior in hooks, not in skill text

## Status

Accepted

## Context

The source toolkits described their approval gates, test requirements, and pull-request rules in
skill prose. A model can skip prose, and content it reads (a work item description, a web page) can
steer it. The team's rules must hold anyway.

## Decision

Every behavior that must always hold is a rule in the hook runtime with a deny test and an allow
test. Skill text explains the rule and how to satisfy it; it is never the enforcement. Behavior no
script can judge stays in the review stage and is documented as review-only.

## Options Considered

- **Skill prose only:** cheap, unenforceable.
- **Post-hoc CI checks:** catches problems after the write to Azure DevOps or the push; too late
  for board writes.
- **Pre-tool hooks (chosen):** see every governed call before it runs, on both hosts.

## Consequences

### Positive

- Rules hold regardless of prompt, model, or injected content.
- Each block names the rule and the fix, so the agent can recover.

### Trade-offs

- A hook runs on every governed call (a Python process start per call).
- Rules must be generic; repository specifics move into `.harness/settings.json`, and tracker specifics into tracker folders.

## Host-specific Impact

Claude Code and Cursor emit different hook events and payloads; one entry point
(`scripts/harness/hook.py --host …`) normalizes both.

## Validation

`tests/harness/test_hook_rules.py` drives the real entry point with both hosts' payload shapes.

## References

- [../architecture.md](../architecture.md)
- [../../05-security/security.md](../../05-security/security.md)
