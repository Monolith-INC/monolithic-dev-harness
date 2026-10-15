---
name: finish-feature-development
description: Close a Feature once all its Stories are done — verify each Story through the tracker, publish closing evidence, and move the Feature to done. With Git-based delivery it also confirms the Story stack landed and opens the Feature pull request. Use after the Feature's last Story is done (and, with Git delivery, after merge-story-stack-into-feature).
---

# Finish feature

Before using the tracker, call `workflow_tracking_status`. If tracking is paused, report that this
skill is unavailable until `/resume-tracker`.

Read the project's settings to see whether the user chose Git-based delivery, then follow the
matching section. Both close the Feature only on evidence read from the tracker.

## Without Git-based delivery

1. **Read the Feature and its Stories** through the tracker (`tracker_get_work_item`,
   `tracker_list_children`).
2. **Verify every Story is done:** each one is in the done state and holds its verification and
   resolution artifacts. Stop and name each Story that is not, without changing anything.
3. **Publish closing evidence** on the Feature with `tracker_publish_artifact`: which Stories it
   holds, what was verified for each, and how each was resolved.
4. **Move the Feature to done** with `tracker_transition_work_item`. One `move-item` approval for
   the Feature covers its closing evidence and the move.

## With Git-based delivery

1. **Read the Feature and its Stories** through the tracker.
2. **Verify every Story is complete:** its required artifacts exist and it is in the done state.
3. **Confirm every Story has landed** on the Feature branch through `merge-story-stack-into-feature`
   (merge commits).
4. **Reconcile** first if an ancestor update is still pending (`reconcile-feature-stack`).
5. **Open the Feature pull request** into the base branch through the SCM adapter, as a **draft**,
   and link it to the Feature. Push and pull request are one `publish-branch` approval.
6. **Publish closing evidence** on the Feature: what was verified and how it was resolved.
7. **Move the Feature to done** only after the evidence and the pull-request link exist. One
   `move-item` approval for the Feature covers both its closing evidence and the move.

## Rules

- Verify every Story's completion through the tracker, not from memory.
- With Git-based delivery, create and link the Feature pull request through the configured SCM
  adapter.
- Publish the verification and closing evidence before requesting done.
