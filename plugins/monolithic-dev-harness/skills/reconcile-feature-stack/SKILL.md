---
name: reconcile-feature-stack
description: Propagate ancestor changes through stacked story branches.
---

# Reconcile feature stack

Before using tracker hierarchy or artifacts, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Use the SCM adapter to inspect the feature and story pull requests, identify ancestor updates, and merge or rebase them into descendants in order. Resolve conflicts explicitly, re-run verification, and publish reconciliation evidence to the associated tracker work item.
