---
name: review-pr
description: Review pull-request threads through the configured SCM adapter and persist decisions to the tracker.
---

# Review pull request

Before publishing the tracker report, call `workflow_tracking_status`. If tracking
is paused, report that this skill is unavailable until `/resume-tracker`.

Retrieve review threads via the configured GitHub or Azure Repos adapter. Classify each as comply, defer, or reject; present the consolidated decision for confirmation; apply comply edits; and reply to rejected threads without changing their status. Publish the review report as a versioned tracker artifact linked to the pull request and work item.

The orchestrator remains an instruction engine. Provider calls go through the workflow-integrations gateway.
