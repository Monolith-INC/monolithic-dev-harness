---
name: finish-feature-development
description: Close a feature after all child stories merge.
---

# Finish feature

Before using tracker completion state, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Fetch the feature and child stories through the tracker adapter, verify required artifacts and story completion (with Git-based delivery, stories already landed via `merge-story-stack-into-feature`), then, with Git-based delivery and only when the user wants one, create the feature-to-protected-branch pull request through the SCM adapter and link it to the feature. Publish the closeout artifacts to the tracker and request the configured logical done transition.

## Without Git-based delivery

Read the Feature and its Stories with `tracker_get_work_item` and `tracker_list_children`. Verify
every Story is done and holds its verification and resolution artifacts; stop and name each one
that is not. Publish the closeout on the Feature with `tracker_publish_artifact`: a
`resolution_report` and a `verification` artifact. Then move the Feature to done with
`tracker_transition_work_item`. One `move-item` approval for the Feature covers its closeout and
the move.

## With Git-based delivery

Also confirm every Story has landed on the Feature branch through `merge-story-stack-into-feature`
(merge commits), and reconcile first if an ancestor update is pending. Open the Feature pull
request only when the user asks (`publish-branch` approval); a pull request is never a condition
for closing. The harness moves a Feature or Epic to done only when every child is done or
cancelled and it holds a `resolution_report` and a `verification` artifact.

The stage sequence is in [`references/stage-workflow.md`](references/stage-workflow.md).
