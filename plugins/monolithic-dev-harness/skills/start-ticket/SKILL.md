---
name: start-ticket
description: Start a configured tracker work item and plan its specification artifacts.
---

# Start ticket

Before using a tracker operation, call `workflow_tracking_status`. If tracking is
paused, report that this skill is unavailable until `/resume-tracker` restores the
configured provider.

Fetch the work item through the configured tracker adapter, confirm (with Git-based delivery only) that the current branch matches the bootstrap-selected {key} convention, and request the logical in_progress transition. Return generic work-item identity, provider state, child items, and the specification artifact plan. Durable state belongs in the configured tracker; for the local tracker, its ticket files in `Tickets/` are the tracker state.

If required specifications are missing, invoke write-spec and publish resulting artifacts through the integration gateway before implementation writes.

## In the harness

`harness next` runs this skill at Execution entry, once the Story is refined, its implementation
plan is approved, its Tasks exist and its preparation documents are approved; the guard refuses
the in_progress transition before that.

1. Read the item with `tracker_get_work_item` and the tracker's rules with `tracker_describe`
   (see [the tracker contract](../../references/tracker-contract.md)).
2. Link the work session: `harness work-session link --work-item <key> --repo <project>`.
3. Ask `harness decision present --gate move-item --value item=<title> --value
   status=<in-progress name> --value ref=<key>`, then move it with `tracker_transition_work_item`.
4. With Git-based delivery only, check out the item's branch (`branch_template` in
   `.harness/settings.json`). Without it, stay in the current working copy: no branch, commit or
   checkout session is needed for local work.
5. Report the item, its state, its children, and the technical spec kinds it still lacks;
   `write-spec` writes those. An approved, unchanged spec is never regenerated.
