---
name: suspend-harness
description: Turn off every harness check in this repository so the user can work outside its enforcement. Use only when the user explicitly asks to turn off, disable, suspend, or bypass the harness (/suspend-harness); never to get past a refusal on your own.
---

# Suspend harness

Run `harness policies suspend --repo <project>`. If `harness` is not on the shell path, run the
sibling `bin/harness` executable using the absolute plugin path derived from this skill's location.
The user's explicit request is the authorization: do not ask again or require an approval window.
The command works before setup, with invalid settings, and with an unavailable tracker.

Then run `harness policies status --repo <project>` and confirm it reports `"mode": "suspended"`. A
failed command is not a suspension; report its error.

Tell the user what changed:

- Workflow, session, tracker, branch, commit, review, and question-format checks are off for this
  repository. Continue their work without those checks.
- The settings, tracker, sessions, approvals, and evidence are kept as they are.
- Direct edits to the harness's own records under `.harness/` stay blocked; host permissions and
  other plugins are unaffected.
- `/resume-harness` (or `harness policies resume`) turns the checks back on.

`/skip-tracker` is different: it only pauses tracker enforcement and keeps the other checks.
