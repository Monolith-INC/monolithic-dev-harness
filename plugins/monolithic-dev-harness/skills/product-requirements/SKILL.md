---
name: product-requirements
description: Create, update, or validate a right-sized Product Requirements Document with stable requirements, explicit scope, user journeys where useful, and measurable outcomes. Use for multi-person or multi-epic alignment; skip it when a concise product spec is enough.
license: MIT
---

# Product Requirements

Produce the organizational agreement on **what and why**, never the implementation design. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) first.
For creation, read [`references/prd-template.md`](references/prd-template.md). For validation and
the pre-handoff review, read [`references/quality-rubric.md`](references/quality-rubric.md).

## Right-skill check

Use a PRD when several people must agree on the product, several epics need one baseline, or the
stakes require formal product decisions. Route a one-pager to `product-brief`, an untested concept to
`forge-idea`, and already-defined single-outcome intent to `product-spec`.

## Create

Start with a brain dump and existing material, then calibrate stakes and choose coaching or fast
path. Elicit rather than author product strategy. For consumer or multi-stakeholder products, ask
the user to narrate key sessions with named protagonists; structure their answers into stable
`UJ-N` journeys. For internal tools or technical products, a capability-led shape may be clearer.

Write `requirements/PRD.md` with stable IDs and only the sections the product needs:

- purpose, vision, target users or jobs, and glossary;
- coherent feature groups;
- globally stable `FR-N` requirements, each with testable consequences;
- cross-cutting non-functional requirements with real bounds;
- non-goals and MVP in/out scope;
- `SM-N` success metrics plus counter-metrics where optimizing the primary metric could cause harm;
- assumptions and open questions.

Implementation choices, transport details, rejected-option matrices, and other earned depth go to
`requirements/addendum.md`. Append decisions to `.decision-log.md` as they land.

## Quality gate

Validate substance rather than section presence:

1. **Decision readiness:** trade-offs and unresolved tensions are visible.
2. **Substance:** no persona, innovation, vision, or NFR theater.
3. **Strategic coherence:** features and metrics serve one thesis.
4. **Done clarity:** every requirement has observable consequences.
5. **Scope honesty:** omissions, assumptions, and deferrals are explicit.
6. **Downstream usability:** stable IDs, terminology, and references resolve.
7. **Shape fit:** rigor matches the product and stakes.

At finalize, reconcile every input and decision-log entry, resolve phase-blocking questions, and
mark the PRD final. Offer `experience-design` and `architecture-spine` only when coordination risk
earns them; every epic still receives its own `product-spec`.

## Update and validate

Update by appending the change decision, preserving IDs, and re-rendering. Surface reversals before
applying them. Validation is read-only, cites exact sections, assigns severity by impact on product
decision quality, and offers an update afterward.

Adapted from BMad Method's PRD workflow and quality rubric (MIT, BMad Code, LLC).
