# Work-session lifecycle process trial — 2026-10-05

- Project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
- Candidate command: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`
- Trial type: direct local CLI process check. No language model or host plugin activation was involved.
- Existing project tracker, settings, and workflow were present before the trial.

## Actions

The command created two work sessions in the same project for separate requests:

- `WS-22ebb757709f` — “Investigate DAY-001 task counts and prepare its plan.”
- `WS-66b279ef2af9` — “Investigate a separate task-count issue, DAY-002.”

It selected the DAY-001 session, paused it, stopped the DAY-002 session, resumed DAY-001, then
stopped both. Listing returned both separate records. The project root recorded in each session
matched the prepared project path.

## Result

Pass: each request remained attached to its own record; the session commands worked without
requiring Git, tracker operations, or setup changes; pause, stop, and explicit resume changed only
the selected record. SHA-256 snapshots of all existing `.harness` files outside the new
`work_sessions` folder were identical before and after. Both test sessions were left stopped.

This proves the candidate CLI and local session storage process. It does not prove that a live
Codex skill automatically offers or selects these records, that workflow or question state is
session-scoped, or that the installed desktop plugin has reloaded the candidate. A separate Luna
trial is checking whether the current harness entry naturally reaches this control.

## Automated coverage

- Nine new `test_work_sessions` cases passed.
- Existing checkout-session and prepared-workflow tests passed in the same focused run.
- Ruff passed for `work_sessions.py`, `cli.py`, and `test_work_sessions.py`.
- Full focused test output: 51 tests passed.
