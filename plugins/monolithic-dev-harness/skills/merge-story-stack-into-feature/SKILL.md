---
name: merge-story-stack-into-feature
description: >-
  This skill should be used when the user asks to "merge story stack into feature",
  "land stacked stories", "absorb user stories into the feature branch",
  "merge stories into feature", or to integrate a stacked Feature after reconcile.
  Merges Story branches into Feature in oldest→newest order with merge commits only;
  never squash or rebase. Hands off to finish-feature-development; does not open
  Feature→trunk.
---

# Merge story stack into feature

Before using the tracker, call `workflow_tracking_status`. If tracking is paused, report that this
skill is unavailable until `/resume-tracker`.

## Before you start

- The Feature branch exists.
- The Story branches form a stack, oldest to newest, and each Story is implemented and reviewed
  (its draft pull request into the Feature branch exists).
- The stack is reconciled: if the Feature advanced after a Story branched, `reconcile-feature-stack`
  has run.

Rebase, squash merges, and force-push are refused by the `history-preserved` rule whenever the
repository is governed; nothing needs switching on.

## Procedure

1. **Identify the Feature branch** from the tracker or the remote.
2. **List the Story branches** in stack order, oldest to newest, from the tracker's child order and
   the pull-request bases.
3. **Skip Stories already landed:** `git merge-base --is-ancestor <story-tip> <feature>`.
4. **Check the next Story is current.** If it does not contain the Feature tip, run
   `reconcile-feature-stack` first, or stop and say why.
5. **Check out the Feature branch** and pull its latest.
6. **For each remaining Story, oldest to newest:**
   1. Make sure its pull request into the Feature branch exists.
   2. Merge it with a merge commit: `git merge --no-ff <story-branch>` locally, or complete the
      pull request with the merge (no-fast-forward) strategy. Never squash.
   3. Resolve any conflicts on the Feature branch, then continue.
   4. Push the Feature branch (approval batch).
   5. Complete or update the Story's pull request to reflect the merge.
   6. Run `reconcile-feature-stack` for the Stories still open, so the next one stays incremental.
   7. Publish evidence of this Story's merge on the Feature work item.
7. **Verify** every Story tip is now an ancestor of the Feature branch.
8. **Stop.** Hand off to `finish-feature-development`; do not open the Feature → base-branch pull
   request here.

After each Story, the Feature contains every commit of that Story, and the Stories still open are
reconciled against the new Feature tip.

## Rules

- Run only when stacked Story branches are ready to land.
- Do not create a new Feature or Story branch here.
- Process unmerged Stories oldest to newest; never skip a middle Story while later ones exist.
- Merge commits only. Never squash a Story into the Feature, never rebase a Story onto it, and
  never force-push the Feature or a Story branch.
- Resolve conflicts on the Feature branch that received the merge.
- Keep every Story pull request's base on the Feature branch; never retarget one to the base
  branch.
- Publish merge evidence on the Feature work item after each Story lands.
