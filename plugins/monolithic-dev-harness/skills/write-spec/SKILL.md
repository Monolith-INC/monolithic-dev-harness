---
name: write-spec
description: Generate tracker-backed specification artifacts with Actor-Critic review.
---

# Write specification

Before publishing to the tracker, call `workflow_tracking_status`. If tracking is paused, report
that this skill is unavailable until `/resume-tracker`.

`write-spec` writes the technical specs a Story still lacks: RFC, ADR, design doc, technical
specification, SRS, bugfix specification or API contract. It never writes an implementation plan:
the Story's plan comes from `generate-breakdown-work-items` and was approved with
`implementation-confirm`. Ask the tracker which spec artifacts the Story already has and write only
the missing kinds; an approved, unchanged spec is never regenerated or approved again. Draft each
from its template and run the shared Actor-Critic critic.

Pass prior critic history explicitly between attempts. The orchestrator keeps retry/reflection state in memory for the invocation; the accepted artifact is published through the tracker adapter with an idempotency revision. Local tracker persists that accepted artifact in its managed tracker records; no separate bypass file is required.

The result identifies artifact scope, required and missing kinds, source hints, the template, critiques, and the next action.

## Inputs

Refinement has already produced the *what*: the Story in its template (acceptance criteria and
points included), its approved implementation plan, and its Tasks. Read them as the spec's input.
Also resolve any `product-spec` referenced by the Story and read every file listed under its
`companions:` field. Trace the Story to its covered `CAP-N` values. Do not restate or re-decide
that intent, and do not restate the plan: link it.

The spec decides the Story-local *how*: affected modules (from the repository's `AGENTS.md`
routing), data and contract changes, test strategy per Task, implementation-level UI details, and
risks. Upstream `AD-N` rules and UX contracts are binding inputs.

When the proposed *how* would change the Story's scope (a capability, acceptance criterion, Task,
UX contract, or architecture invariant), stop. Work items come first: refinement updates the Story
(`enrich-work-item`, or `amend-workitems` for a tree), then its plan is approved again, then its
Tasks change. Never change them silently from here.

The accepted technical spec includes a compact traceability section:

- `CAP-N` → Story acceptance criteria;
- acceptance criteria → Tasks and verification;
- applicable `AD-N` / UX decisions → affected modules.

## Approval

Present the exact accepted spec revision to the user through the best surface the host actually
provides: interactive canvas/document/editor, native rendered preview, an opened file with
structured summary, then faithful inline review. A bare path, unopened file link, or short summary
does not count. Record the content digest and surface used in the workflow checkpoint. Once the
material needed to decide is visible, ask the `approve-spec` gate with the spec as `--artifact`;
pane controls do not record harness approval. That approval covers publishing this spec while it is
unchanged. An edited digest requires a new review. `implement-story` starts only after it.

When the spec lives only in the artifacts path, set its frontmatter to `status: approved` before
you ask. The user's approval pins that exact content; any later edit to the note needs a new
approval.
