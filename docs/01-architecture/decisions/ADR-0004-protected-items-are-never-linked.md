---
title: ADR-0004 Protected items are never linked
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# ADR-0004: Protected work items are never written, linked, or parented

## Status

Accepted

## Context

Teams copy a work item to experiment on it and need the original left intact. In Azure DevOps a
link is two-way: linking a copy to the original also changes the original's relations and bumps
its revision.

## Decision

Ids in `protected_work_items` (`.harness/settings.json`) are refused by the `protected-items`
rule for any write, link, unlink, child creation, or comment, even inside an approval window. The
rule also refuses text that mentions a protected id in a form a tracker turns into a link: each
tracker lists those forms in its manifest (`ids.mention`, with `ids.mentions_link`), for example
`#<id>`, `AB#<id>`, and work item URLs on Azure DevOps, or the bare `ENG-12` on Linear. A copy names the original in plain text (for example `Idea 4007`) instead.

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

`TestProtected` and `TestTrackers` in `tests/harness/test_hook_rules.py`.

## References

- [../../05-security/security.md](../../05-security/security.md)
