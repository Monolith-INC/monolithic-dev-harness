---
name: skip-tracker
description: Pause tracker-backed workflow enforcement for this repository when the user explicitly asks to work untracked. Use only on the user's request (/skip-tracker).
disable-model-invocation: true
---

# Skip tracker

Call `workflow_skip_tracker` through the workflow-integrations gateway. Pausing enforcement is a
human decision: ask the `pause-tracking` gate first; hook `approval-required` requires that
approval for this call, and it is a short general window. The mode is
recorded in `.harness/state/tracking.json`; the selected tracker in `.harness/settings.json` stays as
it is. Confirm that tracker-dependent skills, and the session requirement for code changes, are off
until `resume-tracker` runs. The SCM configuration, Git safety, and the harness rules stay active.
