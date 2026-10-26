---
name: resolve-ticket
description: Resolve a tracker work item with a durable resolution and verification artifact.
---

# Resolve ticket

Before reading or changing tracker state, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Read the work item's specification artifacts and implementation evidence through the tracker and SCM adapters. Produce a resolution report with Problem Recap, Spec Coverage, Implementation Summary, Verification, and Residual Risks. Run Actor-Critic review and publish the accepted resolution_report artifact idempotently.

Before requesting logical done, ensure the tracker contains the resolution and verification artifacts, and the specification artifacts the Story needed. A pull request is the user's choice, never a condition for done; when one exists, link it to the work item. Provider state and artifact checks are enforced by hooks.

## In the harness

Ask `harness decision present --gate move-item` before the done transition. The guard allows it
only when everything the route does for the Story before it holds (`harness workflow requirements
--gate completion` shows the state).
