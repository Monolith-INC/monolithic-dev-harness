---
name: resolve-ticket
description: Resolve a tracker work item with a durable resolution and verification artifact.
---

# Resolve ticket

Before reading or changing tracker state, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Read the work item's specification artifacts and implementation evidence through the tracker and SCM adapters. Produce a resolution report with Problem Recap, Spec Coverage, Implementation Summary, Verification, and Residual Risks. Run Actor-Critic review and publish the accepted resolution_report artifact idempotently.

Before requesting logical done, ensure the tracker contains specification, resolution, verification, and pull-request artifacts and that the SCM pull request is linked to the work item. Provider state and artifact checks are enforced by hooks.
