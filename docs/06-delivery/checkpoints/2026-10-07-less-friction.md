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
