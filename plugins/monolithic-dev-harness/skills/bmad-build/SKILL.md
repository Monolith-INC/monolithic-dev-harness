---
name: bmad-build
description: Technical discovery for a named feature request or ticket, using BMad Build's clarify-and-route and plan steps. Reads the repository, compares feasible approaches, and prepares a reviewed implementation plan before backlog work begins.
---

# BMad Build (harness Stage 0)

After onboarding is verified and the project work session and workflow are active, run:

`harness workflow render --stage discover --session-id <selected-id> --repo <project>`

Use the bundled `bin/harness` if the command is absent from PATH. Read and follow the single
absolute entry path returned in `entry`. Do not execute the templates in this skill folder directly.
On failure, report the output and stop. The command validates and pins a project-specific snapshot;
repeating it verifies and returns the existing snapshot without replacing the run's instructions.

Harness boundaries:

- For a tracker item, read it with `tracker_get_work_item` (and its parent with
  `tracker_list_children` when relevant) and use that record as the intent. Do not move the item,
  create a branch, start a session, or publish anything from this stage.
- Stop at step 2's checkpoint. On **Approve and continue**, save the plan in the harness workflow
  checkpoint and hand it to the backlog stage. Never implement code here; the harness owns
  implementation and review.
- `harness bootstrap` prepares BMad's runtime (`_bmad/`) during session-free onboarding.
  Rendering requires verified setup; it never installs or fetches BMad or repairs project settings.
- Planning needs no Git metadata, commit, branch, or implementation session.
