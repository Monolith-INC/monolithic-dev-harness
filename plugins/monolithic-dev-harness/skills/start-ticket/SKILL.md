---
name: start-ticket
description: Start a tracker work item on its branch: move it to in progress, bind it to this checkout with a session, and plan its specification artifacts. Use at the start of work on a Story, from the harness flow or feature-implementation.
---

# Start ticket

For an approved six-stage bundle, consume its saved implementation plan, manifest and technical
specification. Reuse its contextual approval for stated tracker transitions; do not ask a second
move-item or spec gate. Detect optional version control now. Local implementation never requires a
branch, commit, tracker transition, or checkout-bound session. If the user has chosen tracker or
versioned delivery, perform only its explicitly authorized actions. If tracking is paused or
unavailable, retain local progress and continue local execution.

Before using a tracker operation, call `workflow_tracking_status`. If tracking is skipped, report
that this skill is unavailable until `/resume-tracker` restores it.

1. Fetch the work item with `tracker_get_work_item` and read the tracker's rules with
   `tracker_describe` (see [the tracker contract](../../references/tracker-contract.md)). Before any
   branch or status change, verify that its Implementation Plan is saved, required atomic Tasks are
   present in the selected tracker, and their parent is this Story. If a Task is intentionally
   local-only, verify the user explicitly chose that consequence. Complete missing breakdown first.
2. When the user has selected branch-based delivery and VCS is present, optionally check out the
   work item's branch using `branch_template`. Otherwise remain in the current working copy.
3. If tracker-backed status is part of the approved work, move the item to `in_progress` with
   `tracker_transition_work_item`. It is a tracker write: reuse a valid bundle approval for this stated transition; otherwise ask the
   `move-item` gate with `--value item=<title>`, `--value status=<in-progress name>`, and
   `--value ref=<id>` first.
4. A checkout-bound `harness session` is optional and is used only when the user selected
   branch-based delivery. The project work-session and unchanged implementation-confirm approval
   authorize local edits without tying work to a branch.
5. Report the work item, its provider state, its children, and the specification artifacts it
   needs. If a required specification is missing, consult the user about the gap. In legacy runs, use
   `write-spec`; an unchanged approved bundle never needs spec regeneration or another approval.

Durable state lives in the tracker; for the local tracker, its `.harness/tracker/` records are the
tracker. The session lives in `.harness/state/sessions/` and changes only through `harness session`.
