---
name: product-spec
description: Distill an idea, brief, PRD, UX contract, architecture spine, issue, or mixed notes into a compact canonical product contract with stable capabilities and companions. Use before backlog decomposition when intent is defined; update or validate an existing product spec through the same skill.
license: MIT
---

# Product Spec

This is the canonical transformer between planning and the harness backlog. It distills intent; it
does not discover product strategy. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) first.
When creating or re-rendering the contract, read
[`references/spec-template.md`](references/spec-template.md).

## Workspace and ownership

Write one folder per epic or coherent outcome:

```text
specs/<epic-or-outcome>/
|-- SPEC.md
|-- .decision-log.md
`-- <content-named companions>.md
```

`product-spec` is the only writer of `SPEC.md` and its spec-authored companions. Updates append to
the decision log and re-derive the files. Preserve stable `CAP-N` identifiers; never renumber or
reuse retired IDs.

## Distill

Rich, structured input is extracted without needless questions. Sparse but usable input gets a
choice: guided work through the five fields or an express draft with gaps listed as open questions.
Input too thin to establish the contract routes to `forge-idea` or `product-requirements` instead of
being padded with invention.

`SPEC.md` contains:

1. **Why** — the pain, opportunity, vision, or mandate and who is affected.
2. **Capabilities** — each `CAP-N` has a one-sentence `intent` describing what, not how, and a
   testable or demonstrable `success` condition.
3. **Constraints** — only non-negotiables that rule out a design choice.
4. **Non-goals** — at least one explicit boundary.
5. **Success signal** — the observable world-change that proves the outcome landed.

Unsupported inferences appear under Assumptions; unresolved load-bearing gaps appear under Open
Questions. If a regulated or safety-critical domain implies a missing concern, flag the question;
do not invent the answer.

## Companions and sources

Keep the kernel lean. Content requiring tables, diagrams, glossaries, catalogs, detailed failure
modes, or conventions lives in a content-named companion. Adopted `DESIGN.md`, `EXPERIENCE.md`, and
`ARCHITECTURE-SPINE.md` remain owned by their source skills and are referenced from `companions:`.
Files fully absorbed into the kernel remain under `sources:` for traceability but are not required
reading downstream.

## Self-validation

Before presenting, run two passes:

- **Coherence:** every capability has intent and success; intent is WHAT; constraints bend design;
  non-goals exist; the success signal is demonstrable; IDs are unique and stable; prose is lean.
- **Preservation:** every load-bearing source claim is present in `SPEC.md` or a companion. Record
  intentionally dropped process ceremony rather than silently losing it.

Append both verdicts to `.decision-log.md`. Resolve blocking open questions before backlog handoff.

## Handoff

Present the complete contract and companions, then ask whether to start backlog drafting. On
approval to proceed, `generate-work-item` creates the top ancestor and `decompose-backlog` maps each
Story to the `CAP-N` values it covers. Do not create tracker artifacts from this skill.

Adapted from BMad Method's Spec workflow (MIT, BMad Code, LLC).
