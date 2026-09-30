---
name: experience-design
description: "Create, update, or validate the shared visual and interaction contracts for a product: DESIGN.md for how it looks and EXPERIENCE.md for how it behaves. Use when UX decisions must guide later specs or multiple implementation units."
license: MIT
---

# Experience Design

Elicit and capture the user's design vision; do not impose colors, patterns, or product behavior.
Read [`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) first.
When creating or validating the contracts, read
[`references/contracts.md`](references/contracts.md).

## Outputs

The `ux/` folder owns two peer contracts:

- `DESIGN.md`: brand posture, design tokens, typography, spacing, shape, depth, component visuals,
  and hard visual do/don't rules.
- `EXPERIENCE.md`: form factors, information architecture, voice, behavioral component patterns,
  states, interaction primitives, accessibility floor, responsive/platform behavior, and key flows.

Each may omit irrelevant sections. Existing design systems are inherited by reference; specify only
the product-specific delta. Mockups and wireframes illustrate the contracts but never override them.

## Create

Scan existing product, requirements, spec, research, architecture, brand, and design-system sources;
ask the user which apply. Invite a brain dump, establish form factors and stakes, then choose
coaching, fast path with `[ASSUMPTION]`, or external design handoff.

In coaching, ask the user to narrate key flows with named protagonists and an explicit value moment.
Close the surface map: every stated need must have a surface and every surface a flow that lands
there. Probe gaps instead of inventing screens. Record accepted visual and behavioral decisions in
`ux/.decision-log.md`.

Use visual option artifacts only when seeing materially helps the decision. Clearly label them as
options; the user chooses. Afterward, extract lasting decisions into the two contracts and keep only
useful mockups or wireframes under `ux/mockups/` or `ux/wireframes/`.

## Validate and finish

Check coverage, consistency, accessibility, state completeness, responsive behavior, and source
preservation. Walk every information-architecture surface and identify which has a visual reference
versus contract-only guidance. Resolve blocking assumptions and mark both contracts final.

On update, preserve established token and journey names unless the user explicitly changes them.
Validation is read-only and offers an update. Hand both documents to `product-spec` as adopted
companions; do not copy them into the product contract.

Adapted from BMad Method's UX workflow (MIT, BMad Code, LLC).
