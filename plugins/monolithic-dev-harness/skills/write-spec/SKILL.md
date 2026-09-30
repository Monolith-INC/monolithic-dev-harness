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
implementation plan in the artifacts path). Read them as the spec's input. Also resolve any
`product-spec` referenced by the Story and read every file listed under its `companions:` field.
Trace the Story to its covered `CAP-N` values. Do not restate or re-decide that intent.

The spec decides the Story-local *how*: affected modules (from the repository's `AGENTS.md`
routing), data and contract changes, test strategy per Task, implementation-level UI details, and
risks. Upstream `AD-N` rules and UX contracts are binding inputs. When the proposed *how* would
change a capability, Task, acceptance criterion, UX contract, or architecture invariant, stop and
send the change to its owning skill instead of changing it silently.

The accepted technical spec includes a compact traceability section:

- `CAP-N` → Story acceptance criteria;
- acceptance criteria → Tasks and verification;
- applicable `AD-N` / UX decisions → affected modules.

Present the complete accepted spec to the user for **gate G2** (the Tech Lead's approval). When the
host provides an artifact/document pane, open the spec there; otherwise show it inline, or provide a
faithful section-by-section preview plus its path when the complete document is too long. A bare path
does not count as presentation. Ask for approval in chat after the document is visible; pane controls
do not record harness approval. Publishing it to the tracker is a write, so include it in the approval
batch. `implement-story` starts only after G2.

When the spec lives only in the artifacts path, set its frontmatter to `status: approved` before you ask
for G2. The user's approval pins that exact content, and only then does the spec gate let code edits
through. Any later edit to the note needs a new approval.
