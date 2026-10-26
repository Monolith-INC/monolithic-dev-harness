---
title: Planning and interaction reliability
status: implementation
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-08
---

# Planning and interaction reliability

The human authorized four steps: separate planning from implementation enforcement; remove
misplaced validation/size gates; attempt native controls with graceful fallback; repeat acceptance
on a fresh copy before implementation.

## Boundaries

Publication and protected-state rules remain intact. Missing source globs remain conservative for
code; only Markdown inside the configured, non-root artifacts directory is classified as planning.
Explicit source globs win. Recursive deletion, source files, arbitrary documentation and symlink
escapes do not inherit this exception.

A Breakdown task is bookkeeping, not coding. Its Done transition requires one published
`planning_completion` receipt bound to its ID, Story parent and complete set of other published
Task children. The title must identify Breakdown; title alone is insufficient. JSON content is:
`{"purpose":"breakdown","item_id":"TASK-0005","parent_id":"STORY-0001","children":["TASK-0001","TASK-0002","TASK-0003","TASK-0004"]}`.
Use one stable receipt title and increasing numeric revisions. The highest revision supersedes
older records; conflicting records at the highest revision are denied. Corrections remain
publication writes requiring the relevant approval.
The batch publication review includes the receipt and transition. Ordinary implementation completion
still requires its own session and resolution, verification and PR evidence.

## Validation and scope

Draft critics run once per submitted draft. Transport success means the critic ran; the report
may still say FAIL. The actor can revise and resubmit without implementation approval. Reflection
can signal stalled review, with findings retained; a fresh review cycle does not reset an
implementation task or grant publication permission. Both orchestrator surfaces share the critic.

Plan length is advisory. Splitting is offered only for identified independently shippable goals,
never because a cohesive feature has several acceptance checks or exceeds a token estimate.

## Interaction

Codex defaults to attempting blocking native questions. Async-only capability uses
`--async-available`; explicitly unavailable controls use `--native-unavailable`. Existing fallback
preserves the decision and review. Hook registration and transcript recovery accept bare and
`functions.` native names. Only actual human responses can resolve a decision.

## Verification and acceptance

Regression coverage must include planning edits with missing globs, explicit source precedence,
recursive writes, symlinks, genuine coding-task completion denial, malformed/mismatched/duplicate
receipts, validator findings and reflection continuity, both exposed orchestrators, native name
routing, capability selection and existing approval negatives.

Repeat setup, discovery, Deepen, publication and backlog completion on a fresh factory-created
fixture. The actual chat workspace must be that fixture for the live native trial. Do not claim
live capture from subprocess hook fixtures or a parent-mediated child exchange. Preserve real
controls, human replies, saved decisions and all failures. Stop before application implementation.
