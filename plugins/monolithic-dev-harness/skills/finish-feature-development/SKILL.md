---
name: finish-feature-development
description: Close a Feature after all its Stories have landed on the Feature branch — verify each Story is done, open the Feature pull request into the base branch, link it, publish closing evidence, and move the Feature to done. Use after merge-story-stack-into-feature.
---

# Finish feature

Before using the tracker, call `workflow_tracking_status`. If tracking is paused, report that this
skill is unavailable until `/resume-tracker`.

## Procedure

1. **Read the Feature and its Stories** through the tracker.
2. **Verify every Story is complete:** its required artifacts exist and it is in the done state.
3. **Confirm every Story has landed** on the Feature branch through `merge-story-stack-into-feature`
   (merge commits).
4. **Reconcile** first if an ancestor update is still pending (`reconcile-feature-stack`).
5. **Open the Feature pull request** into the base branch through the SCM adapter, as a **draft**,
   and link it to the Feature. Push and pull request are one approval batch.
6. **Publish closing evidence** on the Feature: what was verified and how it was resolved.
7. **Move the Feature to done** only after the evidence and the pull-request link exist (approval
   batch).

## Rules

- Verify every Story's completion through the tracker, not from memory.
- Create and link the Feature pull request through the configured SCM adapter.
- Publish the verification and closing evidence before requesting done.
