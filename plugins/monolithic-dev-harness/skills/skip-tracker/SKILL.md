---
name: skip-tracker
description: Pause tracker-backed workflow enforcement for this repository when the user explicitly asks to work untracked. Use only on the user's request (/skip-tracker).
disable-model-invocation: true
---

# Skip tracker

Call `workflow_skip_tracker` through the workflow-integrations gateway. Pausing enforcement is a
human decision: hook `approval-required` requires the user's approval batch for this call. Report the saved adapter
and confirm that tracker-dependent skills are unavailable until `resume-tracker` runs. The SCM
configuration, Git safety, and the harness the harness rules stay active.
