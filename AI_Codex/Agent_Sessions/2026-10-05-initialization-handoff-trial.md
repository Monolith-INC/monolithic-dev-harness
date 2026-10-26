# Initialization handoff process trial

## Result

All three read-only `bootstrap --inspect` runs agreed on the project, settings, confirmed English choice, saved request, workflow checkpoint, next action, suspended policies, and lack of an outstanding harness question. The handoff carried the isolated user-state directory and the bundled command correctly. No workflow action was advanced.

This verifies the candidate process handoff only. It does not verify activation through an installed native host. The human's recorded “Stop” in the separate focused-test fixture was not replayed or treated as an answer to this process test; the fixture notes that its call identifier differs. The inspected project itself reports `waiting_for_answer: false` and `pending_question: null`.

## Runs and counts

- Candidate: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`.
- Model/reasoning context: GPT-6 Luna, medium reasoning (assigned test context; this is not a claim that the harness CLI invokes a model).
- Commands: three inspections. First from `/tmp/monolithic-dev-harness-trial-locw4ixf` with explicit `--repo`; second from the target project using the returned project path, command, and `HARNESS_USER_STATE_DIR`; third as a separate hash-bracketed integrity check using that same returned handoff.
- Reads: one supplied session record; five target configuration/state files (settings, workflow, language confirmation, policy state, and isolated preferences); one bootstrap skill; one setup implementation excerpt; one CLI help invocation; one bounded text search and one target file listing. The inspection process itself reported the fields retained in the evidence JSON. No application source files were read.
- Writes: this report and its JSON evidence sibling only.

## Context comparison

All three inspection responses were byte-for-byte equivalent as JSON. They report project root and working directory `/tmp/monolithic-dev-harness-trial-locw4ixf/project`; command `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`; and environment `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

All three report tracker and source control as `local`, artifacts at `/tmp/monolithic-dev-harness-trial-locw4ixf/project/docs/planning`, language `en` with `language_confirmed: true`, and setup `ready`. All preserve the original request to continue backlog item `DAY-001-task-counts.md` through planning and artifacts, stopping before implementation. All report the same active workflow at point 4, “Approved DAY-001 discovery plan,” stage `backlog`, with the next action to draft, enrich, decompose, and break down local work items for human batch review, without publishing. All report policies suspended, no pending question, and no wait for an answer.

No missing or inconsistent context was seen between the two returned handoffs. There is a distinction between the process fixture's recorded human stop and this project's inspected checkpoint: the former has a separate call identifier, while the latter reports no pending harness question. I did not reconcile or alter those records.

## Separate hash-bracketed integrity check

For the additional read-only inspection only, SHA-256 was captured immediately before and after the command. Both values matched for settings (`37829d62a173bb07d1edc8c1c76e16aa4a81629c291ac492199b7a7aafe42dce`) and workflow (`f2ffabb7fcf005411a700d88d04f5c248c4f62747c0fa6e21588828ea9e4b9bd`). The third inspection returned the same handoff as the first two. This establishes no change during that additional inspection; the first two inspections still lack their own pre-run hashes.
