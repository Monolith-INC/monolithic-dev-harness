---
name: resume-tracker
description: Resume tracker-backed workflow enforcement after it was paused with skip-tracker.
---

# Resume tracker

Call `workflow_resume_tracker` through the workflow-integrations gateway. Report the tracking mode it
returns. From then on, governed code changes need an active session again (`start-ticket`).
