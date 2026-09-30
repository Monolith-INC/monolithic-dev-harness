---
name: plan-initiative
description: Route a raw idea through the smallest useful discovery and product-planning path, ending in a compact product spec ready for backlog decomposition. Use when the user wants to explore, validate, plan, define, or architect an idea before creating work items or starting implementation.
license: MIT
---

# Plan Initiative

Conduct the pre-backlog planning layer. Favor the source method's principle: planning tools are
independent and optional; use only the ones needed to turn the current input into a defined intent.

Read [`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) first.

## Route from the gap

Inspect the user's input and existing artifacts before asking questions.

- No useful options yet → `brainstorm-ideas`.
- A held but untested idea → `forge-idea`.
- A decision needs current evidence → `research-decision`.
- A clear concept needs a concise narrative → `product-brief`.
- Several people, teams, or epics need one requirements baseline → `product-requirements`.
- Product look, behavior, accessibility, or key flows can diverge → `experience-design`.
- Separately built units could make incompatible technical choices → `architecture-spine`.
- Intent is defined → `product-spec`.

These are not fixed stages. Run them in any order, revisit an owner when a downstream conflict is
found, and skip work that does not reduce uncertainty. Do not force a PRD on one-person or
single-outcome work whose intent is already clear.

## Size the path

- **Small/local outcome:** a defined intent may go directly to backlog creation or the existing
  delivery flow.
- **Epic-sized outcome:** finish one `product-spec`, then decompose it into ordered Stories.
- **Multi-epic initiative:** use shared requirements, UX, and architecture only where coordination
  risk earns them, then create one `product-spec` per epic.

## Finish planning

Planning is complete when the product spec passes its preservation and coherence checks, blocking
open questions are resolved, and any load-bearing UX or architecture artifacts are listed as
companions. Present the complete contract and explicitly ask whether to begin backlog drafting.

Beginning backlog work is a new action. Do not create work items merely because planning finished.

Adapted from BMad Method's planning router (MIT, BMad Code, LLC).
