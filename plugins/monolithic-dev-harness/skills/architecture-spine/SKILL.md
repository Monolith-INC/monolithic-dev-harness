---
name: architecture-spine
description: Create, update, or validate a lean architecture spine containing the cross-unit invariants that independently built parts must share. Use before backlog decomposition for multi-epic, cross-system, high-risk, or otherwise coordination-heavy work; not for Task-level code sketches.
license: MIT
---

# Architecture Spine

Produce a consistency contract, not an exhaustive solution document. Read
[`../../references/planning-artifacts.md`](../../references/planning-artifacts.md) first.
When creating or re-rendering the spine, read
[`references/spine-template.md`](references/spine-template.md).

The inclusion test is strict: if two units one level down built this independently, could they
choose incompatibly? Record the decision only when the answer is yes, the choice is non-obvious,
and a real trade-off exists. Otherwise defer it or let compliant code own it.

## Scope and altitude

Set the scope and altitude from the input:

- initiative spine keeps Features coherent;
- Feature spine keeps Epics coherent;
- Epic spine keeps Stories coherent.

A child spine inherits the parent's decisions as read-only constraints. A conflict is surfaced to
the parent; never weakened locally. For brownfield work, inspect the actual repository and adopt
existing conventions rather than designing a parallel system.

## Coach the load-bearing calls

Default to coaching unless the user asks for speed. Name a coherent design paradigm first, then
work through boundaries and dependency direction, state mutation, shared-data ownership,
integration contracts, error and security boundaries, deployment/environment invariants, and other
dimensions that can create cross-unit divergence. Show realistic alternatives and your lean; the
user decides. Verify current versions and fit before naming technologies.

Record decisions and rationale in `architecture/.decision-log.md`. Stable `AD-N` identifiers are
never renumbered or reused.

## Output

Write `architecture/ARCHITECTURE-SPINE.md` with:

- scope, altitude, named paradigm, and inherited invariants;
- one block per decision: `AD-N`, `Binds`, `Prevents`, and enforceable `Rule`;
- consistency conventions;
- minimal stack and structural seed, explicitly owned by code after cold start;
- `CAP-N` → architecture mapping when a product spec exists;
- diagrams only where they convey dependency or deployment shape; and
- explicit deferred decisions with the condition that should reopen them.

Keep rationale in the decision log, not the spine. A whole relevant dimension left silent is a gap;
a dimension explicitly deferred is a decision.

## Review and handoff

Check every `AD-N` has all three fields, inherited IDs resolve, diagrams are valid, technology
claims are current, capabilities have a home, and the spine contains no decision that could safely
be read from code. Reconcile all load-bearing inputs before finalizing.

On update, append the new decision and re-render while preserving IDs. Validation is read-only and
offers an update. `product-spec` adopts the spine as a companion. The later `architect` skill turns
an approved Story into code shapes within this spine; it does not replace or override it.

Adapted from BMad Method's Architecture Spine workflow (MIT, BMad Code, LLC).
