---
name: brainstorm-ideas
description: Facilitate divergent idea generation before product planning, then converge only when the user is ready. Use when the user asks to brainstorm, ideate, generate options, or get beyond the obvious approaches.
license: MIT
---

# Brainstorm Ideas

Generate a broad option space before evaluating it. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) for persistence
and handoff rules.

## Set the stance

Confirm the topic, the goal behind the session, and one stance:

- **Facilitator:** supply prompts and techniques, never ideas.
- **Creative partner:** facilitate and contribute ideas, clearly attributing them.
- **Ideate for me:** run the divergent pass autonomously and present the result.

Hold the stance for the run. In dialogue, ask one generative prompt at a time.

## Diverge

Do not organize or conclude too early. Change creative domain or technique every 5–10 turns, using
constraints, analogies, inversions, stakeholder viewpoints, combinations, and failure-first prompts.
Aim well beyond the first obvious batch; breadth matters more than polished wording.

Append every idea and meaningful direction to `idea/.decision-log.md` when persisting. Do not turn
raw ideas into requirements during divergence.

## Converge

Converge only when the user asks or the topic is exhausted. Cluster by underlying opportunity, name
surprising combinations, and evaluate against criteria derived from the session goal. Preserve
minority ideas with high upside instead of averaging everything into safe consensus.

Produce `idea/BRAINSTORM-INTENT.md` containing only the selected directions, rejected directions
whose reason matters, decision criteria, and unresolved questions. Offer `forge-idea` for pressure
testing or `product-spec` when the chosen intent is already defined.

Adapted from BMad Method's brainstorming workflow (MIT, BMad Code, LLC).
