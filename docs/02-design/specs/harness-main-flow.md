---
title: Harness Main Flow
status: implementation
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-08
---

# Harness main flow

![Six-stage flow](../../assets/diagrams/harness-main-flow.svg)

Discovery → Planning → Hardening → Preparation → Confirmation → Execution.
The [implementation plan](six-stage-onboarding-implementation.md) defines delivery and verification.
The bundled [stage contract](../../../plugins/monolithic-dev-harness/references/six-stage-onboarding.md)
is the agent-facing source of truth.

## User experience

Discovery investigates before asking. Once the work is understood, choose Light, Standard or
Hardcore planning depth before drafting. Comprehensive paths offer a contextual shortlist,
full method catalog or agent recommendations. Retain Reshuffle, List all and Proceed.
Hardening validates the resulting plan; it is distinct from exploring approaches before drafting.

Preparation assembles relevant specifications, requirements, risk findings and companions, then
creates a reading manifest and implementation plan. Evidence and decisions are saved throughout.
Tracker artifacts are drafted locally. One final confirmation accepts the reviewed bundle and
its specified actions. Already accepted decisions are recapped, not repeatedly approved.
Merging and unrelated external writes remain context-bound actions.

## Runtime boundaries

Native controls are first, followed by async native and faithful chat fallback. Failed delivery
is not an answer. Active-mode stop enforcement requires a staged decision rather than an untracked
prose menu. Suspension disables that enforcement and every other harness veto; observation may
retain genuine replies but cannot authorize an unreviewed action.

Language defaults to English if no preference is recorded. Free mode requires no session.
Progress can be saved while paused or waiting for an answer. Pause, resume, reset, restart and
drop preserve existing evidence. Changed circumstances trigger consultation, not blanket approval
expiry. Versioning is detected automatically at execution entry and is optional.

## BMAD alignment

Adopt evidence-first investigation and Code Maps, contextual elicitation, stakes-calibrated
reviewers, input reconciliation, coherence/preservation checks, lean specifications and companions.
The unified lifecycle, depth profiles, reading manifest and reliable native transport are harness
responsibilities. Do not copy upstream's pre-planning VCS gate or make every improvement blocking.

## Verification limits

The acceptance trial captured two blocking replies and one async reply, then continued with checks
suspended before quota interrupted it. Those observations prove those exchanges, not the entire
new workflow. A fresh live trial is required after regression verification; do not overwrite the
concurrent acceptance report or replace genuine host evidence with simulated approvals.
