---
name: bmad-build
description: Technical discovery for a named feature request or ticket, using BMad Build's clarify-and-route and plan steps. Reads the repository, compares feasible approaches, and prepares a reviewed implementation plan before backlog work begins.
---

# BMad Build (harness Stage 0)

Read fully and follow `workflow.md` in this skill's folder. It is BMad Build's workflow, rendered for
the harness: step 1 clarifies and routes the request, step 2 investigates the repository and writes
the plan from `plan-template.md`.

Harness boundaries:

- For a tracker item, read it with `tracker_get_work_item` (and its parent with
  `tracker_list_children` when relevant) and use that record as the intent. Do not move the item,
  create a branch, start a session, or publish anything from this stage.
- Stop at step 2's checkpoint. On **Approve and continue**, save the plan in the harness workflow
  checkpoint and hand it to the backlog stage. Never implement code here; the harness owns
  implementation and review.
- `harness bootstrap` prepares BMad's runtime (`_bmad/`); `workflow.md` says how to prepare it if it
  is missing. Never install or fetch BMad from another source, and never ask the user to repair it.
- Planning needs no Git metadata, commit, branch, or implementation session.
