# PRD Shape

This is expert prior knowledge, not a checklist. Keep the essential spine unless a section is
genuinely irrelevant; add concern-specific sections when the product needs them.

```markdown
---
title: <product>
status: draft | final
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []
---

# Product Requirements: <product>

## Purpose and Vision

<Audience, product thesis, why it matters.>

## Target Users and Jobs

- <specific user or job-to-be-done>

## Key User Journeys

### UJ-1 — <named protagonist and outcome>

- **Context:** <who, where, why>
- **Entry state:** <authentication, device, prior state>
- **Path:** <ordered concrete beats>
- **Value moment:** <how the protagonist knows value landed>
- **Resolution:** <resulting state>
- **Failure path:** <important recovery, when applicable>

## Glossary

- **Term** — <one canonical meaning>

## Features and Functional Requirements

### <Feature>

<Behavioral description and relevant UJ-N references.>

#### FR-1 — <capability>

<Actor> can <outcome> under <conditions>.

**Testable consequences**

- <observable condition>

**Out of scope**

- <boundary, when non-obvious>

## Cross-Cutting Requirements

- **NFR-1:** <specific measurable or verifiable bound>

## Non-Goals

- <explicit exclusion>

## MVP Scope

### In

- <item>

### Out

- <item and reason when load-bearing>

## Success Metrics

- **SM-1:** <definition and target>. Validates <FR-N>.
- **SM-C1:** <counter-metric and why it must not be optimized>.

## Assumptions

- [ASSUMPTION] <unconfirmed inference>

## Open Questions

- <answerable decision question>
```

## Adapt-in concerns

Add sections when the concern is real: system-wide performance/security/reliability, privacy and
cost guardrails, platform behavior, monetization, stakeholder approvals, business case, SLAs and
support, integrations, rollout/change management, data governance, regulatory compliance, public
API and versioning policy, or hardware/environmental limits.

Technical choices and mechanism detail belong in `addendum.md`, UX contracts, or the architecture
spine—not in product requirements.
