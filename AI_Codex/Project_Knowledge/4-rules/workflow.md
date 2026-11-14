---
id: "4-rules/workflow"
tier: 4
type: "rules"
area: "workflow"
title: "Approval, delivery and completion rules"
read_when: "Checking a change against the project definition of done and approval rules."
provenance: "stated"
sources:
  - "CONSTITUTION.md"
  - "docs/03-engineering/development.md"
  - "docs/03-engineering/testing.md"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[3-mechanics/testing]]"
  - "[[2-structure/directory-conventions]]"
---

## Summary

Work items are the source of truth, and people own approvals. The definition of done is explicit in the development guide.

## Mandated

The documented outcome gate passes locally and in CI. Changed rules need both deny and allow tests through hook.py. User-visible changes are reflected in docs/, and releases also update CHANGELOG.md. Durable documents belong to their work item. Tracker mutations go through the harness gateway for harness-owned operations.

## Prohibited

Do not manufacture human approval or grant authority from a status report. Do not publish or merge pull requests as an automatic prerequisite for closing a work item: Article 10 makes pull requests the user’s choice. Do not treat an unapproved draft plan as binding policy.

## Enforcement

Constitution articles, workflow policy, approval records, tests and review evidence.

## Open questions

- This review setup makes Linear authoritative for review requirements; migrating the harness local backlog itself is not part of this setup.
