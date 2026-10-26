---
name: feature-implementation
description: Plan and implement a feature using tracker hierarchy and stacked SCM branches.
---

# Feature implementation

Before using tracker hierarchy or artifacts, call `workflow_tracking_status`. If
tracking is paused, report that this skill is unavailable until `/resume-tracker`.

Use the generic tracker contract to fetch a feature and its user stories and confirm logical states and acceptance criteria. Each Story is delivered from its own approved implementation plan; there is no plan covering several Stories. With Git-based delivery, use the SCM adapter for the feature branch and one story branch per child story.

The branch convention is selected during bootstrap and must be confirmed from `branch_template` in `.harness/settings.json`; do not invent a provider-specific naming rule. When the user wants pull requests, open story pull requests against the feature branch, reconcile ancestor changes before new descendant commits, land stacked stories with `merge-story-stack-into-feature`, and hand off to finish-feature-development after all stories merge.

## In the harness

Run the Story flow once per Story, in dependency order, each as `harness next` gives it:
`start-ticket` → `write-spec` (only missing kinds) → `implement-story` → `review` →
`resolve-ticket`. Without Git-based delivery, work in the current working copy, with no branches,
commits or pull requests, and close the Feature with `finish-feature-development` in its local mode.
A pull request is always the user's choice, never a condition for closing a Story or the Feature.
Every tracker write, push and pull request goes through the approval protocol in the `harness`
skill.

The stage sequence is in [`references/stage-workflow.md`](references/stage-workflow.md).
