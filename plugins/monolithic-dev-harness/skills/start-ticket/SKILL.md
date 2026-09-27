---
name: start-ticket
description: Start a tracker work item on its branch: move it to in progress, bind it to this checkout with a session, and plan its specification artifacts. Use at the start of work on a Story, from the harness flow or feature-implementation.
---

# Start ticket

Before using a tracker operation, call `workflow_tracking_status`. If tracking is skipped, report
that this skill is unavailable until `/resume-tracker` restores it.

1. Fetch the work item with `tracker_get_work_item` and read the tracker's rules with
   `tracker_describe` (see [the tracker contract](../../references/tracker-contract.md)).
2. Check out the work item's branch, named by `branch_template` in `.harness/settings.json` with the
   id in the form the tracker's `ids.branch_key` accepts (`branch-and-pr` → *Branch*).
3. Move the item to `in_progress` with `tracker_transition_work_item` (a tracker write: it needs an
   approval window).
4. Bind it to this checkout: `harness session start <work item>`. The command refuses when the
   branch carries a different id or the checkout already has an open session. Governed code
   changes are refused until a session is active; `harness session pause` / `resume` / `close`
   change it, and `harness session status` shows it.
5. Report the work item, its provider state, its children, and the specification artifacts it
   needs. If a required specification is missing, run `write-spec` and publish the result through
   the gateway before any implementation write.

Durable state lives in the tracker; for the local tracker, its `.harness/tracker/` records are the
tracker. The session lives in `.harness/state/sessions/` and changes only through `harness session`.
