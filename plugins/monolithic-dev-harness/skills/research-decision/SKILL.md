---
name: research-decision
description: Research a product, market, domain, competitor, user, or technical question in service of a named decision, producing a cited decision brief. Use when planning depends on current evidence rather than more ideation.
license: MIT
---

# Research Decision

Research serves a decision. It is not a general information dump. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) for source and
workspace rules.

## Frame

Name the decision, the alternatives or uncertainty, the evidence that could change the decision,
the needed freshness, and the effort appropriate to the stakes. Infer a useful research lens:
market, domain, technical, competitive, user voice, or academic literature. A selection decision
must state candidates and criteria before gathering evidence.

Present the research plan before an expensive, long, or paid run. Ordinary current web research may
proceed when it is within the user's request.

## Gather and verify

Prefer primary and authoritative sources. Every material claim records publisher, publication date,
access date, and a direct link. Cross-check consequential claims with independent sources when
available. Separate verified claims, contested claims, inference, absence of evidence, and stale
evidence. Never turn search snippets or uncited model knowledge into findings.

## Synthesize

Write `research/<topic>/RESEARCH.md` with:

- the decision and recommendation;
- evidence that most affected it;
- alternatives and trade-offs;
- verified, uncertain, and overturned claims;
- limitations and what would change the conclusion; and
- citations adjacent to each supported claim.

Append research decisions and load-bearing claims to the folder's `.decision-log.md`. Hand the
short decision and constraints—not the raw source pile—to `product-brief`, `product-requirements`,
`architecture-spine`, or `product-spec`.

Adapted from BMad Method's Deep Recon workflow (MIT, BMad Code, LLC).
