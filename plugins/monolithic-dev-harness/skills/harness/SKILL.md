---
name: harness
description: Default entry point when the user asks to add, build, change, or fix a meaningful feature in a project, even if they do not mention the harness or provide a tracker item. Start with technical discovery for feature requests, then follow the product and delivery workflow as requested. Also use when the user asks to take an idea or work item through the whole process, asks what comes next in a harness run, or asks how the process works. Keep small mechanical edits on the direct path.
---

# Harness

Follow [six-stage onboarding](../../references/six-stage-onboarding.md): Discovery → Planning →
Hardening → Preparation → Confirmation → Execution. Choose depth after discovery and before
drafting. Present one final bundle confirmation; reuse its unchanged decisions and approvals.
No versioning prerequisite applies before execution.

Use the bundled `bin/harness` when `harness` is unavailable on PATH.
Onboarding is optional. If the user wants skills or guidance without a session, use
`harness mode free --repo <project>` and invoke the relevant skill directly. Free mode preserves
all action approvals and protected-state rules; it is not suspension. Ideation can be added to
ongoing work without restarting that work.
Start with `harness begin --request "<exact request>" --repo <project>`.
It checks setup, routes the session, creates the workflow when absent, and returns pinned discovery instructions.

- `setup_needed`: follow the bootstrap skill, preserving the returned request, then repeat begin.
- `free`: provide the requested guidance or skill without creating a session or requiring setup.
- `choose_session`: offer its candidates and Start new through native controls; repeat begin with the chosen `--session` or `--new`.
- `waiting_for_human`: present the saved question through the best available host control.
- Active discovery: read the returned `discover_entry` and follow it. Later stages: follow the saved next action.
- Paused or terminal work: consult the user; never silently restart it.

## Just-in-time references

Read [stage guide](../../references/harness-stage-guide.md) for the current stage, approval boundaries,
suspension, or recovery. Read [human decisions](../../references/human-decisions.md) when asking a question;
read [storyboard](../../references/workflow-storyboard.md) when changing stage or navigating saved work.
Do not preload all references at startup.

Use catalog gates in the selected language; keep native controls and gracefully fallback via
`harness decision fallback`. A hook-recorded answer needs no `decision status` call;
For Codex, invoke the native tool returned by `decision present`; do not replace it with a chat
menu when callable. Use `--async-available` for async-only hosts, or `--native-unavailable` when
no native control is callable. Default Codex presentation attempts blocking buttons.
use status only for recovery when capture is uncertain. A gate with `--artifact` automatically saves
its review checkpoint when a workflow exists. Save manual checkpoints at stage completion or material
progress without a question. Communication works without any active session.
Language is optional: use the captured project choice, saved preference, or English. Never stop
because language confirmation or capture is missing. Optional preferences do not block progress.
`harness onboarding skip|dismiss|restart|reset|drop|pause|resume --repo <project>` controls onboarding
without a session and preserves engineering evidence.

`workflow prepare` is optional reference material, not a mandatory capability-declaration ceremony.
Discover tools at the point of use and report genuinely missing capabilities. Explicit `--available`
remains available for diagnostic validation. Inspect plan size and advisory scope signals with
`harness plan check <file> --repo <project>`.

Keep investigation subagents, scope decomposition, formal Deepen, adversarial review, and verification
from the stage workflows. Approved artifacts and context-bound writes retain the recorded approval
rules; reduced bookkeeping never grants permission. Consult the user when relevant circumstances change.
