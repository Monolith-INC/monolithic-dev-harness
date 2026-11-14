---
id: "4-rules/security-compliance"
tier: 4
type: "rules"
area: "security"
title: "Authority and security constraints"
read_when: "Checking whether a change weakens approval, provider trust or protected state."
provenance: "stated"
sources:
  - "CONSTITUTION.md"
  - "docs/05-security/security.md"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[4-rules/runtime-budgets]]"
---

## Summary

Provider sign-in, the user’s approval and runtime evidence are separate forms of authority.

## Mandated

The security model requires human approval for tracker/source-control writes and pushes. Settings, approval records, tracker trust and session state have human-owned authority. An onboarded adapter is trusted only as reviewed.

## Prohibited

Do not forge approval, host events, process identities, answers or completion evidence. Do not weaken controls to make a trial pass. Do not store provider credentials in project configuration.

## Enforcement

Deterministic runtime checks, trusted host evidence and explicit provider boundaries. The documentation acknowledges that not every specialized Codex tool invokes hooks.

## Open questions

- The owner supplied no additional regulatory requirement in this setup.
- The security document’s old timeout wording conflicts with current hook-budget constants; the code-derived budget unit records the current implementation.
