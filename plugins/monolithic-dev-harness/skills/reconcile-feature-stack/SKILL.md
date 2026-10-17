---
name: reconcile-feature-stack
description: Propagate ancestor changes through stacked story branches.
---

# Reconcile feature stack

Before using tracker hierarchy or artifacts, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Use the SCM adapter to inspect the feature and story pull requests, identify ancestor updates, and merge them into descendants in order (merge commits only: the harness's `history-preserved` rule denies rebase and force-push). This skill runs only with Git-based delivery. Resolve conflicts explicitly, re-run verification, and publish reconciliation evidence to the associated tracker work item.

The stage sequence is in [`references/stage-workflow.md`](references/stage-workflow.md).
