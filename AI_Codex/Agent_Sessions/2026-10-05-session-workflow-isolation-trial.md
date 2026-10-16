# Session-scoped workflow process trial — 2026-10-05

- Project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
- Candidate command: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`
- Trial type: direct local CLI process check; no language model or native host was involved.
- Existing legacy project workflow, settings, and tracker records were hashed before and after.

## Actions

The trial resumed each saved work session, started a workflow using that session's exact request,
saved a discovery checkpoint, read it back, then stopped the work session again:

- `WS-22ebb757709f` — “Investigate DAY-001 task counts and prepare its plan.” Its checkpoint
  retained `Continue WS-22ebb757709f`.
- `WS-66b279ef2af9` — “Investigate a separate task-count issue, DAY-002.” Its checkpoint retained
  `Continue WS-66b279ef2af9`.

Each workflow file lives beside its work-session record. Both work sessions ended stopped.

## Result

Pass: the two workflows kept separate requests and checkpoints; each could be read by its own
session id. A stopped session can be inspected but cannot save new workflow progress until resumed.
All prior `.harness` files outside `work_sessions` had matching SHA-256 hashes before and after,
including the existing project-wide workflow, setup, and tracker state.

This verifies candidate CLI/storage behavior on the reusable project. It does not verify selection
through the installed Codex skill or session-specific pending-question handling; the installed
entry trial separately stopped at the older checkout-bound command.
