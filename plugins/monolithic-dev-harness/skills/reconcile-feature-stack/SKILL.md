---
name: reconcile-feature-stack
description: Carry changes from an earlier branch in a Feature stack into the Story branches built on it, oldest to newest, with merges only. Use when the Feature branch or an earlier Story branch changed after a later Story branched from it, before adding commits to the later Story, and after each Story lands.
---

# Reconcile feature stack

Before using the tracker, call `workflow_tracking_status`. If tracking is paused, report that this
skill is unavailable until `/resume-tracker`.

## Procedure

1. **Inspect the stack.** List the Feature's Story pull requests through the SCM adapter.
2. **Order it.** Determine the stack order from the tracker's child order and the pull-request
   bases, oldest to newest.
3. **Merge each ancestor into its descendant, in order.** The first open Story takes the Feature
   branch as its ancestor. A later Story takes the previous Story as its ancestor while that
   previous Story is not yet merged into the Feature. Merge only (`git merge`); never rebase, since
   the Story branches already have open pull requests.
4. **Resolve conflicts** on the Story branch that received the merge.
5. **Push** each reconciled Story branch before moving to the next one (`publish-branch` approval for that branch).
6. **Re-run the checks** (`check`) after each update.
7. **Publish evidence** of the reconciliation on the Feature work item.

## Rules

- Run only when an ancestor (the Feature or an earlier Story) advanced after a descendant branched.
- Do not create a new Feature or Story branch here.
- Process open Story branches oldest to newest, and never skip a middle Story while later ones
  exist.
- Merge the immediate ancestor into each Story before moving to the next. Never rebase, and never
  force-push.
- Keep every Story pull request's base on the Feature branch; never retarget one to the base
  branch.
- Never open the Feature → base-branch pull request here.
