---
title: "Slice 1: the user's answers cannot be lost"
type: ticket
---

Finished slice 1 of the assurance redesign on branch `fix/slice-1-answers-cannot-be-lost`
(pull request 54), cut as `0.7.0-rc.14`. Plan: `.superpowers/plans/2026-11-12-slice-1-answers-cannot-be-lost.md`.
Tasks 2 to 6 approved by Théo with IMPLEMENTATION APPROVED on 2026-11-14.

## Ledger

- Task 0 (`638eac3`), Task 1 (`e07baf2`): done in the Nov 12 session.
- Task 2: every hook event runs under `scripts/harness/hook_budget.py`, counted from process start
  (12 s before a tool call, 7 s for the others). A timeout records nothing and names a way out that
  changes with each repeat (show again, type the number, `harness suspend`). Once an answer starts
  being recorded the event finishes. New guard name `hook-budget`.
- Task 3: a dialog or chat question matches on wording and options, so it can always be shown
  again. The decision keeps its own `id`; `presentation_id` is the host's id of the newest showing;
  `presented_on` lists transports. A late answer to an older dialog is not recorded. Codex async
  delivery keeps its rule.
- Task 4: each showing records its conversation (`presented_in`). A typed reply answers only in a
  conversation that was shown the question (`decisions.presented_here`); with no conversation
  known, a chat or async question counts as shown, a dialog one only once shown. Replaces the
  Codex-only origin check on typed replies.
- Task 5: `tests/harness/test_hook_invariants.py` (rules 1 and 4).
- Task 6: `tests/harness/test_trial_8307_replay.py`, then the release: version sources and
  CHANGELOG at `0.7.0-rc.14`.
- Plan deviation: none in the tasks. One finding from my own review of Task 3 was fixed in that
  task's commit: a question no command prepared kept its first dialog's id, so a late answer to
  that dialog was still accepted.
- Existing tests changed in setup only: `test_typing_after_a_dismissed_picker_answers_it` now shows
  the picker before typing (the new rule needs a showing), and the three id assertions in
  `test_question_fallback.py` and `test_prepared_native_question_binds_once` (now "binds to its
  latest showing") follow the new id meaning.

## Verification

- New tests were run against the code before each change and failed there: `test_present_again.py`
  (3 of 4), `test_typed_reply.py` (2 of 5), the late-answer test (1).
- Full gate on 2026-11-14, from the repo root: ruff check and format clean; shellcheck clean;
  `tests/run.sh` 341 backlog tests and 2329 harness tests passed (1 skipped), installer checks
  passed; `check_versions.py` all sources at 0.7.0-rc.14; `claude plugin validate` passed for the
  plugin and the marketplace.
- Baseline before the slice's Tasks 2 to 6: 2293 passed, 1 skipped.

## Still open

- The live trial of rc.14, by Théo. Afterwards read `.harness/state/hook-timing.log` from the run.
- Known limit: for Claude, a question prepared straight into the chat has no conversation recorded,
  so a typed reply from any conversation counts until a dialog shows it.
