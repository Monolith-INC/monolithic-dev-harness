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

Before using tracker hierarchy or artifacts, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Activate stage conditioning: write `merge-story-stack-into-feature` to
`.codex-workflows/active-stage` at start so hooks deny rebase, force-push, and
squash-oriented git. Delete that file at STOP.

Follow `.agent/workflows/workflows-merge-story-stack-into-feature.md` and obey
every rule in `.agent/rules/rules-merge-story-stack-into-feature.ts`. Use the
SCM adapter for Story→Feature pull requests and merge-commit completion only.
Use the tracker adapter to publish per-story merge evidence on the Feature work
item. Invoke `reconcile-feature-stack` when required by the workflow. After all
Stories land, hand off to `finish-feature-development` — do not open Feature→trunk.
