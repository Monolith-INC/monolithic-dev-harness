---
name: finish-feature-development
description: Close a feature after all child stories merge.
---

# Finish feature

Before using tracker completion state, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Fetch the feature and child stories through the tracker adapter, verify required artifacts and story completion (stories already landed via `merge-story-stack-into-feature`), then create the feature-to-protected-branch pull request through the SCM adapter. Link the pull request to the feature, publish the closeout artifact to the tracker, and request the configured logical done transition.
