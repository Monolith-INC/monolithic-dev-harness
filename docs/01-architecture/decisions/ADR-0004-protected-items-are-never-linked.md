---
title: ADR-0004 Protected items are never linked
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# ADR-0004: Protected work items are never written, linked, or parented

## Status

Accepted

## Context

Teams copy a work item to experiment on it and need the original left intact. In Azure DevOps a
link is two-way: linking a copy to the original also changes the original's relations and bumps
its revision.

## Decision

Ids in `azure.protected_work_items` are refused by the `protected-items` rule for any write, link,
unlink, child creation, or comment, even inside an approval window. The rule also refuses text
that mentions a protected id as `#<id>` or by work item URL, because Azure DevOps turns a mention
into a link. A copy names the original in plain text (for example `Idea 4007`) instead.

## Options Considered

- **Allow "related" links only:** still modifies the original.
- **Block everything touching the id (chosen).**

## Consequences

### Positive

- The original's revision never changes because of the harness.

### Trade-offs

- The copy has no navigable link back; the plain-text name in the description replaces it.

## Host-specific Impact

None.

## Validation

`TestProtectedItems` in `tests/harness/test_hook_rules.py`.

## References

- [../../05-security/security.md](../../05-security/security.md)
