---
name: write-spec
description: Generate tracker-backed specification artifacts with Actor-Critic review.
---

# Write specification

Before publishing tracker artifacts, call `workflow_tracking_status`. If tracking
is paused, report that this skill is unavailable until `/resume-tracker`.

Use the work-item description, requirements, and implementation context supplied by the tracker adapter. Select logical artifact kinds (RFC, ADR, design doc, technical specification, implementation plan, bugfix specification, or API contract), draft them, and run the shared Actor-Critic critic.

Pass prior critic history explicitly between attempts. The orchestrator keeps retry/reflection state in memory for the invocation; the accepted artifact is published through the tracker adapter with an idempotency revision. Local tracker persists that accepted artifact in its managed tracker records; no separate bypass file is required.

The result identifies artifact scope, required and missing kinds, source hints, the template, critiques, and the next action.
