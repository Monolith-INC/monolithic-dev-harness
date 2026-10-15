---
name: start-ticket
description: Start a tracker work item: move it to in progress, link the work session to it (and check out its branch with Git-based delivery), and report which technical spec kinds it still lacks. Use at the start of work on a Story, from the harness flow or feature-implementation.
---

# Start ticket

Consume the Story's approved implementation plan, the reading manifest and any approved technical
specification. Each tracker transition is asked with its own `move-item` approval. Detect optional
version control now. Local implementation never requires a
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
   `tracker_transition_work_item`. It is a tracker write: ask the `move-item` gate with `--value item=<title>`, `--value status=<in-progress name>`, and
   `--value ref=<id>` first.
4. Link the project work session to this Story or Bug:
   `harness work-session link --work-item <key> --repo <project>`. Code changes start only when
   `harness workflow requirements --repo <project>` reports `ready`: the session is linked, the
   tracker holds the item in progress with its Tasks parented to it, and an approved, unchanged
   implementation plan names it. The requirements come from the workflow catalog; when one is
   missing, the report names the stage and skill that produce it. Go there and continue; it is a
   workflow step, not an error to report to the user. Version control plays no part.
5. A checkout-bound `harness session` is optional and is used only when the user selected
   branch-based delivery; it gives no permission to change code.
6. Report the work item, its provider state, its children, and the specification artifacts it
   needs. When a technical spec kind is still missing, `write-spec` writes it; an approved,
   unchanged spec is never regenerated or approved again.

Durable state lives in the tracker; for the local tracker, its `.harness/tracker/` records are the
tracker. The work session lives in `.harness/state/work_sessions/` and changes only through
`harness work-session`.
