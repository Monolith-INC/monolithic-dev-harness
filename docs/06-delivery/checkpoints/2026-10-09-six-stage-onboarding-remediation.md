---
title: Six-stage onboarding remediation checkpoints
status: in-progress
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-09
---

# Checkpoints

1. **Corrected trial basis and recorded plan.** The earlier draft pointed at the wrong run
   (`six-stage-1571ba0`). Corrected plan and handoff to the actual `test-003` fixture and its
   project-local `acceptance-result.md`. Recorded the method-menu instruction conflict, 18m41s
   elapsed after Proceed with a factual activity summary, user-reported UI visibility failure, and
   the preconfigured-fixture limitation. No prior acceptance evidence was changed.
2. **Native elicitation and confirmation contract.** Replaced BMad's mandatory prose menu with a
   paginated formal-decision protocol respecting the three-option limit, preserving ordered
   multi-selection and fallback. Clarified artifact visibility and trial approval boundaries in
   the six-stage contract; removed silent-fallback language from the storyboard and removed the
   inaccurate tracker-write promise from the confirmation option detail. Added a focused test for
   the documented interaction contract. Focused harness tests passed (104); the full plugin suite
   passed (1,296 tests, 1 skipped, 296 subtests). Ruff lint/format, TOML parsing, targeted
   Markdown lint and whitespace checks passed. The repository-wide Markdown run also found one
   heading-spacing issue in the pre-existing untracked `six-stage-1571ba0/result.md`; that prior
   trial record was left untouched. The remaining `HALT and give the user a choice`
   matches are in separate planning/review workflows outside the advanced-elicitation path and
   need triage before claiming a repository-wide UI cleanup.
3. **Clean acceptance fixture prepared.** Created `/tmp/monolithic-dev-harness-trial-80zre_yv/project`
   from the canonical template with the `unconfigured` profile. Recursive comparison against the
   template passed (excluding Git metadata); no harness settings/state or BMad runtime were
   seeded. Saved the minimal run request and setup provenance under
   `docs/06-delivery/acceptance/six-stage-41c4466-clean/`. Installed the committed 0.6.2 Codex
   plugin build from source revision `41c4466`; selected installed files match. Clickable
   questions are enabled. Desktop restart is still required before the live run. At the user's
   request, recreated the same clean fixture with the supported helper at `temp/test-004/project`;
   it matches both the original `/tmp` copy and template. The original is pending safe cleanup.
