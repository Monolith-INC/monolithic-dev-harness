---
name: harness
description: Default entry point when the user asks to add, build, change, or fix a meaningful feature in a project, or to work on a work item (an id or a tracker link), even if they do not mention the harness. Also use when the user asks to take an idea or work item through the whole process, asks what comes next in a harness run, or asks how the process works. Keep small mechanical edits on the direct path.
---

# Harness

The harness knows the workflow's order; you do not have to. Its route runs Discovery → Planning →
Hardening → Refinement → Preparation → Execution → Verify, and it computes the next step from what
is already done: the work items, the approvals and the documents.

1. Start with `harness begin --request "<the user's exact request>" --repo <project>`, run on its
   own as one plain command (`--repo .` or an absolute path; no variables, `$(…)`, `;` or `&&`).
   Use the bundled `bin/harness` when `harness` is not on PATH.
2. Do exactly the step in its `next` field:
   - `skill`: invoke that skill and follow it as it is written. When `discover_entry` is set, the
     skill starts there.
   - `gate`: ask that question with `harness decision present --gate <gate>` (with the `--value`s
     and `--artifact`s the step names), never in your own words.
   - `command`: run it, replacing `<key>` with the work item's key.
   - `say`: what the step is for, and anything to do before asking.
   - `missing`: what is not true yet, and how it becomes true.
3. When the step is done, run `harness next --repo <project>` and do the step it gives. Repeat
   until it answers `complete`.

Never invoke a stage skill that `harness next` did not name, and never skip ahead: a guard refuses
an action whose earlier steps are not done, and its refusal names the step to do instead.

Other states `begin` and `next` can return:

- `setup_needed`: follow the bootstrap skill, keeping the request, then run `begin` again.
- `free`: give the requested guidance or skill without a session.
- `choose_session`: offer its candidates and Start new as a menu; run `begin` again with the
  chosen `--session` or `--new`.
- `waiting_for_human`: the user has not answered the saved question; show it again with
  `harness decision fallback`.
- `tracker_unreachable`: recover or reload the owning `workflow-integrations` gateway before one
  bounded read. Do not start another provider or replay a write with an uncertain outcome.
- Paused work: ask the user before resuming; never restart it silently.

Questions: every question goes through `harness decision present` (a gate by `--gate`, or a
one-off with `--question` and `--option`s). Show the material a question is about before asking
it. If the native control fails, use `harness decision fallback`. Read
[human decisions](../../references/human-decisions.md) when asking.

`harness mode free --repo <project>` gives skills and guidance without a session; approvals and
protected records still apply. The user can suspend every harness check by sending
`harness suspend`; never ask them to.
