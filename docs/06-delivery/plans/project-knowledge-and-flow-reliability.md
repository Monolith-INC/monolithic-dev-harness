---
title: Project knowledge and workflow reliability
status: in-progress
created: 2026-10-09
---

# Project knowledge and workflow reliability

## Goal

Make a harness run predictable from any supported starting point: agents can retrieve bounded,
source-backed project guidance before exploratory reads; planning artifacts follow a deliberate
dependency order; local implementation never requires a VCS or a branch; and the user sees one
confirmation for an unchanged approved bundle.

## Evidence

- The DAY-001 test-004 transcript shows a normal implementation request blocked by a branch/session
  requirement. The run then created `STORY-0001` and `feature/STORY-0001-task-counts` to proceed.
- The same run re-presented implementation confirmation while correcting the plan's metadata and
  refreshing readiness state, despite no renegotiated intent.
- Existing onboarding documentation says tracker drafts precede the implementation plan, but the
  run created its local tracker item during execution. `start-ticket` and `implement-story` still
  prescribe branch creation and per-task commits without making absence of VCS operationally safe.
- `Project_Knowledge` uses a tiered catalog, bounded find/fetch, provenance, freshness, and open
  questions rather than loading the corpus. Harness knowledge tooling exists but only seeds a
  settings pointer and is not required by discovery entry instructions.
- Scrum Guide: backlog items are ordered and refined into transparent, sufficiently granular work;
  Sprint Planning selects items and creates the work plan. Thus preparation should establish the
  candidate work-item hierarchy/drafts before the implementation plan references them.

## Work

1. Document the Project_Knowledge information architecture and transfer its useful deterministic
   retrieval contract to the harness knowledge store; add bounded `catalog`, `find`, and `fetch`
   guidance, provenance/open-question rules, and tests.
2. Make discovery/implementation skills consult the harness knowledge index first, then verify
   source files as needed. Missing, stale, empty, or unavailable knowledge is a non-blocking
   fallback, never a workflow stop.
3. Reconcile the six-stage storyboard and skills with the actual order: discovery; depth/method
   selection; plan hardening; preparation of requirement/spec/risk companions and tracker item/task
   drafts; manifest over the complete bundle; implementation plan referencing that bundle; one
   confirmation. Tracker publication remains explicitly authorized and separate.
4. Remove mandatory Git/VCS, branch, and commit steps from local execution. Keep VCS detection
   automatic and optional; PR/push actions appear only when the user asks for that delivery route.
   Find and remove corresponding enforcement that blocks local source changes solely due to no
   branch/session identity, while retaining independent security and external-write approvals.
5. Add regression coverage for VCS-free execution, tracker-before-plan ordering, knowledge-first
   routing and non-blocking retrieval failures, and approval reuse for unchanged bundles. Audit
   related instructions for conflicting mandatory requirements.
6. Record each meaningful change in the checkpoint log and run focused plus repository checks.

## Acceptance

- From a clean, unconfigured project, harness guidance points the agent to the deterministic
  knowledge query before broader repository reads and falls back without blocking if no useful
  unit exists.
- Local tracker work-item/task drafts exist before the implementation plan is finalized; the plan
  and manifest include their paths and digests.
- One approval remains valid for the unchanged bundle through execution handoff. Internal metadata
  normalization or readiness refresh does not prompt again; material scope/content changes do.
- No VCS, initial commit, branch, or commit is required to implement and verify locally. If VCS is
  present, it is detected automatically and its use follows the user's delivery preference.
- User can always proceed with local work when an optional tracker, knowledge query, or VCS adapter
  is unavailable; only a real missing product decision or explicitly requested external write can
  pause dependent actions.

## Verification

Run focused Python tests for knowledge, onboarding ordering, workflow approvals, and hook policy;
run lint/format and the full plugin test suite. Use the recorded DAY-001 run as regression evidence,
not as a clean acceptance fixture. Prepare a new clean fixture for the next live trial after code
checks pass; do not mutate the preserved test-004 evidence or task implementation.

## Boundaries

Do not alter DAY-001 product source, publish tracker records, push, merge, change global host
settings, or delete existing acceptance evidence as part of this pass.
