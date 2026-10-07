---
title: Agent friction implementation checkpoints
status: complete
owner: maintainers
last_reviewed: 2026-10-07
---

# Agent friction implementation checkpoints

Scope: approved F1–F6 audit in the main-flow specification. No merge or deployment.

1. **F1 — consolidated startup.** Completed the inherited `begin` draft. Setup failures return the request; session ambiguity remains a human choice. Existing workflows are reused, paused workflows stay paused, corrupt records and render failures propagate instead of being silently replaced.
2. **F3 — review checkpoints.** Presenting a question with artifacts saves their digests, pending question and next action in an existing workflow. Session-free and paused-workflow questions still work; unchanged answered decisions reuse their answer without an extra checkpoint.
3. **F5 — plan inspection.** Added `plan check` with word count, explicitly approximate token count and advisory scope signals. It does not claim a tokenizer-exact count or automatic decomposition verdict.
4. **F2/F4/F6 — instruction overhead.** Replaced the large entry skill with a short router and moved detailed stage instructions into a just-in-time reference. Answer-status checks are recovery-only; prepare and manual capability declarations are optional. Native controls, fallback, recorded approvals and deep investigation remain required.
5. **Verification.** Added startup reuse, paused recovery, artifact-checkpoint and missing-plan regressions. The first full run passed 332 backlog tests and 734 main tests, with one obsolete instruction-location assertion failing. Updated that assertion to validate the router link and stage-guide discovery route. The focused rerun passed 56 tests (one skipped); seven friction regressions and 13 approval-reuse/friction checks also passed. Final full-run results follow below.

The estimated roundtrip reduction remains an audit target, not a measured end-to-end result.

Entry skill reduced from 332 lines to 38; detailed instructions remain available in the stage guide. Ruff lint/format, repository checks, Markdown lint and diff whitespace checks passed.

Final full-suite rerun: 332 backlog tests passed; 737 main tests passed, one skipped, 277 subtests passed; installer confirmation checks passed. The final focused run also passed all seven friction regressions.

## Thermos remediation checkpoints

1. **Checked lifecycle and decomposition.** Extracted startup orchestration and a shared checked
   lifecycle. `begin` and explicit resume verify discovery before activation at every stage.
   New-session creation no longer selects it before startup rendering succeeds. Failed rendering
   preserves the previous selection. Focused startup/session/discovery run: 60 passed. The CLI is
   now 809 lines before extracting decision coordination. Design boundaries are recorded in
   `docs/02-design/specs/pr-36-recovery-contracts.md`.

2. **Recoverable decision/checkpoint writes.** New question validation and decision persistence
   precede checkpoint projection. The pending record owns expected and intended workflow versions
   until projection/cleanup complete. Failed writes and interruption recover without duplicate
   points; conflicting progress is preserved. Answer capture completes recovery before resolving.
   The focused decision/workflow/reuse run passed 42 tests; further crash/corruption regressions
   are included in final verification.
3. **Successful-startup host binding.** Added a protected completion receipt and a paired pre/post
   host protocol. Pre-tool guards still run first; completion must match conversation, tool call,
   command, invocation and receipt before binding. Failed, stale, unarmed and replayed completions
   cannot switch context. Codex/Claude hook fixtures exercise startup, then native question and
   human-answer capture in the selected session. Initial binding/security run: 42 passed. Added
   executor aliases, storage-failure and missing-identity cases for final verification. Cursor
   retains its existing session-free conversation model. Live host compatibility remains pending.
4. **Interruption and pending-question boundaries.** A second thermos pass found three additional
   cases: failed first startup was eligible for implicit selection; successful binding followed by
   failed cleanup left a reusable receipt; selecting a pending session omitted its complete question
   and binding evidence. Deferred startup eligibility now requires an atomic selection witness.
   Consumption is saved with the binding and survives later switches. Pending recovery returns the
   complete question without advancing; the same pending scope can be recovered, but another
   unanswered bound scope or a global question cannot be bypassed. The focused run passed 52 tests;
   two additional same-scope/global-gate cases are included in final full-suite verification.
5. **Final verification and re-review.** Full runner: 332 backlog tests and 19 subtests passed;
   786 main tests and 277 subtests passed, one skipped; installer confirmation checks passed.
   Ruff lint/format, repository checks, Markdown lint and whitespace checks passed. Both thermos
   reviewers found no remaining implementation blockers after correcting the global-only recovery
   check. The CLI is 776 lines. These results establish local behavior, not live host compatibility;
   the demo-project walkthrough and measured time savings remain pending before merge readiness.
