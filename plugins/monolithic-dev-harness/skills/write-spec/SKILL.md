---
name: write-spec
description: Generate tracker-backed specification artifacts with Actor-Critic review.
---

# Write specification

Before publishing tracker artifacts, call `workflow_tracking_status`. If tracking
is paused, report that this skill is unavailable until `/resume-tracker`.

Use the work-item description, requirements, and implementation context supplied by the tracker adapter. Select logical artifact kinds (RFC, ADR, design doc, technical specification, bugfix specification, or API contract), draft them, and run the shared Actor-Critic critic. The Story's implementation plan is not a spec kind here: it comes from `generate-breakdown-work-items` and was approved with `implementation-confirm`.

Pass prior critic history explicitly between attempts. The orchestrator keeps retry/reflection state in memory for the invocation; the accepted artifact is published through the tracker adapter with an idempotency revision. Local tracker persists that accepted artifact in its managed tracker records; no separate bypass file is required.

The result identifies artifact scope, required and missing kinds, source hints, the template, critiques, and the next action.

## In the harness

Write only the kinds the Story still lacks (ask the tracker with `tracker_list_artifacts`); an
approved, unchanged spec is never regenerated or approved again. Refinement already produced the
*what* (the refined Story, its approved plan, its Tasks): read them as input and link the plan,
never restate it. When the proposed *how* would change the Story's scope, stop: the work items are
updated first (`enrich-work-item`, or `amend-workitems` for a tree), then the plan is approved
again.

Write each spec where `harness document path --type <kind> --item <story key>` says (`tech-spec`,
`design-doc`, `adr` or `api-contract`) with `status: draft`. Show it with `harness workflow show
--artifact <spec>` and ask `harness decision present --gate approve-spec --artifact <spec>`; set
`active` once approved. The approval pins its content (the `status` line aside); any other edit
needs a new approval.
