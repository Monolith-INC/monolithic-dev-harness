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

## Harness handoff

In a harness run, the backlog stage has already produced the *what*: the Story, its acceptance
criteria, points, and its atomic Tasks from `generate-breakdown-work-items` (with that skill's
implementation plan in the artifacts path). Read them as the spec's input. Do not restate or
re-decide them. The spec decides the *how*: architecture and affected modules (from the repository's
`AGENTS.md` routing), the data and contract changes, the test strategy per Task, UI and design notes,
and risks. When the *how* would change a Task or a criterion, stop and send it back to the backlog
instead of changing it silently.

Present the accepted spec to the user for **gate G2** (the Tech Lead's approval). Publishing it to the
tracker is a write, so include it in the approval batch. `implement-story` starts only after G2.
