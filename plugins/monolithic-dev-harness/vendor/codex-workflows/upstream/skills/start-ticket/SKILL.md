---
name: start-ticket
description: Start a configured tracker work item and plan its specification artifacts.
---

# Start ticket

Before using a tracker operation, call `workflow_tracking_status`. If tracking is
paused, report that this skill is unavailable until `/resume-tracker` restores the
configured provider.

Fetch the work item through the configured tracker adapter, confirm the current branch matches the bootstrap-selected {key} convention, and request the logical in_progress transition. Return generic work-item identity, provider state, child items, and the specification artifact plan. Durable state belongs in the configured tracker; for local tracker, its managed `.local-tracker/` records are the tracker state.

If required specifications are missing, invoke write-spec and publish resulting artifacts through the integration gateway before implementation writes.
