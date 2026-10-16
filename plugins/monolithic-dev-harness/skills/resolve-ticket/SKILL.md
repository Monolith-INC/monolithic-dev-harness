---
name: resolve-ticket
description: Resolve a tracker work item with a durable resolution and verification artifact.
---

# Resolve ticket

Before reading or changing tracker state, call `workflow_tracking_status`. If
tracking is skipped, report that this skill is unavailable until `/resume-tracker`.

Read the work item's specification artifacts and implementation evidence through the tracker and SCM adapters. Produce a resolution report with Problem Recap, Spec Coverage, Implementation Summary, Verification, and Residual Risks. Run Actor-Critic review and publish the accepted resolution_report artifact idempotently.

Before requesting logical done, ensure the tracker contains the resolution and verification artifacts. A pull request is the user's choice: link it when one was opened, but never require it. The workflow hook checks these artifacts on the work item of this checkout's active session, and refuses to complete any other item from here. Once the item is done, close the session with `harness session close`.
