---
name: suspend-harness
description: Explain how the user turns off every harness check in this repository so they can work outside its enforcement. Use when the user asks to turn off, disable, suspend, or bypass the harness (/suspend-harness).
---

# Suspend harness

Only the user can suspend the harness: the hook records it from their own message, and no command
or tool call lets an agent do it. Ask the user to send this as its own message, with nothing else in
it:

```text
harness suspend
```

It works before setup, with invalid settings, and with an unavailable tracker. After they send it,
run `harness suspension status --repo <project>` (or the sibling `bin/harness` from this plugin)
and confirm it reports `"mode": "suspended"`. Never try to suspend the harness yourself, and never
ask the user to suspend it to get past a refusal they did not ask about.

Tell the user what changes while it is suspended:

- Workflow, session, tracker, branch, commit, review, and question-wording checks are off in this
  repository.
- Approval, trust, manual-check, and adoption clicks are still recorded.
- The settings, tracker, sessions, approvals, and evidence are kept as they are.
- Direct edits to the harness's own records under `.harness/` stay blocked; host permissions and
  other plugins are unaffected.
- Sending `harness resume`, or `/resume-harness`, turns the checks back on.

`/skip-tracker` is different: it only pauses tracker enforcement and keeps the other checks.
