---
description: Merge stacked Story branches into the Feature branch in stack order
rules: rules-merge-story-stack-into-feature.ts
---

# workflows-merge-story-stack-into-feature

## Given

- Active Feature branch exists
- One or more Story branches form a stack (oldest → newest dependency)
- Stories are ready to land into Feature (implementation complete; a Story→Feature PR only when the user wants one)
- Stack has been reconciled when Feature advanced after a descendant branched

## Sequence

1. IDENTIFY Feature branch name from ledger, tracker, or remote
2. LIST Story branches in stack order (oldest → newest) from tracker children and SCM PR bases
3. SKIP Stories already contained in Feature (`git merge-base --is-ancestor <story-tip> <feature>`)
4. IF the next unmerged Story does not contain Feature tip as ancestor THEN RUN `reconcile-feature-stack` (or STOP with explicit fail) before merging
5. CHECKOUT Feature branch
6. PULL Feature branch latest
7. FOR each remaining Story in stack order (oldest unmerged → newest):
   1. IF the user wants pull requests THEN ENSURE a Story→Feature pull request exists (base = Feature)
   2. MERGE Story into Feature via merge commit only
      - Local: `git merge --no-ff <story-branch>`
      - SCM: complete PR with Merge / no-ff — never Squash
   3. IF conflicts THEN RESOLVE on Feature branch THEN CONTINUE
   4. PUSH Feature branch
   5. COMPLETE or UPDATE the Story PR, when one exists, to reflect the merge
   6. RUN `reconcile-feature-stack` for remaining open descendants so the next Story PR stays incremental
   7. PUBLISH per-story merge evidence on the Feature work item
8. VERIFY every Story tip is an ancestor of Feature (or Story unique commits are contained in Feature)
9. STOP — do not open Feature→trunk (hand off `finish-feature-development`)

## Loop invariant

After each Story iteration, Feature contains all commits of that Story at merge time; remaining open descendants have been reconciled against the new Feature tip.
