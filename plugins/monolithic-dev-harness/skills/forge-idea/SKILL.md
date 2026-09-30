---
name: forge-idea
description: Pressure-test a half-formed product, feature, or business idea until it is hardened, killed, or materially clearer. Use when the user asks to forge, challenge, stress-test, clarify, defend, or attack an idea before planning it.
license: MIT
---

# Forge Idea

The goal is better thinking, not an artifact or a path to implementation. A killed idea is a
successful cheap result. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) for workspace
rules.

## Open

Establish the idea, whether the user wants to clarify it, test whether it holds, or improve it, and
whether it changes an existing product. For brownfield work, inspect the real project evidence
before accepting claims about it.

Tell the user they may say `attack this`, `defend this`, or `switch roles`. Ask one question at a
time, in dependency order. Start with the load-bearing claim, not feature details. Name fuzzy or
overloaded terms and require a precise choice.

## Apply pressure

Offer a concrete best hypothesis when it helps the user react. Challenge unchecked assumptions,
economics, incentives, adoption, operational cost, failure modes, and simpler substitutes. Use
distinct perspectives such as buyer, user, operator, finance, compliance, or competitor, but keep
the exchange focused rather than staging a panel performance.

Append decisions, assumptions, cracks, rejected branches, and locked decisions to
`idea/.decision-log.md`. Do not praise or agree merely to keep momentum.

## Exit honestly

- **Hardened:** write `idea/FORGED-IDEA.md`, kept very short: settled decisions, rejected options,
  reasons, constraints, and remaining risks.
- **Killed:** record the decisive failure and why further planning is not justified.
- **Clearer:** record what became clear and leave the unresolved idea in conversation; no synthetic
  brief is required.

Offer `product-brief` when a narrative is useful, `research-decision` when evidence is missing, or
`product-spec` when the intent is already complete. Do not steer toward building.

Adapted from BMad Method's Forge Idea workflow (MIT, BMad Code, LLC).
