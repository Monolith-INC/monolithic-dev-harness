---
title: Planning and interaction reliability checkpoints
status: in-progress
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-08
---

# Checkpoints

1. **Housekeeping.** Started on feat/less-friction. Published the pending capture diagnosis and
   merged stacked PRs 32–36 (existing CI green), synchronized main at d0d6e7a and created
   codex/planning-and-interaction-reliability. Preserved permission-only differences in
   /tmp/harness-pre-housekeeping.patch; files owned by another account were not reowned.
2. **Investigation.** Traced planning Markdown classification and generic completion enforcement.
   Independent BMad-guided investigations identified unchanged-draft retry loops, lost findings,
   missing cross-call reflection history, native flags defaulting silently to chat, namespaced
   hook/recovery gaps, and size-based forced splitting. Scope remains the four approved steps.
3. **Planning boundaries.** Excluded only bounded planning Markdown when source globs are absent;
   explicit source patterns, recursive writes and symlinks to source retain code classification.
   Breakdown closure verifies a task/parent/child-bound published receipt without a checkout
   session. Highest numeric revision supersedes old receipts; ties remain denied. Publication
   approvals and ordinary implementation completion are unchanged.
4. **Draft critics and interaction.** Shared a typed single-evaluation critic between both
   orchestrators, preserved findings on errors, restored caller reflection history and retained
   general task authorization. Codex now attempts native blocking presentation by default, with
   explicit async/unavailable paths. Namespaced hook/recovery names are supported. Removed the
   length-only split gate; independently shippable scope remains a human decision.
5. **Review corrections.** Thermos identified shell symlink bypass, receipt revision recovery and
   a missing physical validator test fixture. Fixed these and removed nested orchestrator/global
   runtime-path coupling. Focused revised suite passed 61 tests and 3 subtests. Final full suite
   and re-review were pending at this checkpoint. Prepared a fresh factory fixture for direct-workspace acceptance.
6. **Verification.** Both independent reviewers cleared the corrected implementation. Final
   suites passed 337 backlog tests plus 19 subtests, and 913 main tests plus 277 subtests, with
   one skip. Installer confirmation checks passed. Ruff lint/format, repository/link checks,
   version checks, Markdown (57 files) and whitespace checks passed. ShellCheck is unavailable;
   no shell files changed. One earlier run exhausted temporary storage; preserved its log and
   removed only this run's disposable npm cache before the successful rerun. Evidence logs are
   `/tmp/harness-planning-verified.log` and `/tmp/harness-planning-final.log`.
7. **Live acceptance remains pending.** Prepared a rollback archive before installation.
   Subprocess routing tests do not prove desktop capture. The next trial must use the fresh
   project as the actual chat workspace after a desktop restart, stopping before app code.
8. **Committed and installed.** Pushed source revision `774a484` and opened draft PR 37.
   Supported Codex installation completed; 585 unchanged source files match the cache, and the
   installer-generated `.mcp.json` matches its staged Codex configuration. Doctor reports healthy
   but explicitly does not test live capture. Rollback archive is held privately under
   `/tmp/harness-planning-install-backup-*`; do not publish it. Desktop restart and the real trial
   remain outstanding; neither the draft PR nor these checks establish desktop acceptance.
