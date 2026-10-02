---
date: 2026-09-29
type: ticket
work_item_type: User Story
provider: local
parent_id: ""
language: en
tags: [ticket, story, tech-debt, maintainability]
---

# Simplify the 0.3.0 plumbing flagged by the thermos quality review

## Objective

Pay down the structure debt that the 0.3.0 branch (`feat/adoption-and-session-hardening`) added.
The quality review found the design sound but the plumbing duplicated and ad hoc. None of these
items changes behaviour, so they were deferred past the release. Each one should leave the code
shorter.

## Scope

### Included

1. **One question dispatcher in `scripts/harness/hook.py`.** Tracker, manual (**Approve change**),
   adoption (**Approve adoption**), and generic **Approve** questions each pin a detail at ask time
   and settle it at answer time, but each is wired in by hand:
   - `handle_ask` has three copy-pasted "detail is None → deny `plain-questions` → return 0" blocks.
   - It then merges detail dicts of different shapes (`{**tracker, **manual, **adoption}`).
   - `handle_answer` settles them in an implicit order through `case _: pass` fall-through.
   - The PostToolUse `hookSpecificOutput` print is copied four times.
   - `tool_input` is re-normalized four times.

   Replace all of this with a table of `QuestionKind(name, pin, deny_reason, settle)`:
   - `handle_ask` stores `{"kind": name, **pinned}` for exactly one kind, and denies a question
     that offers two approval kinds at once. Today such a question is silently merged.
   - `handle_answer` calls `KINDS[kind].settle(...)` and then one `_post_note(note)`.
   - The manual-note wording is also duplicated in `handle_prompt`; share it.
2. **`scripts/harness/questions.py` helpers.**
   - Extract `_labels(question) -> frozenset[str]` and `_clicked(tool_input, tool_response)`.
     They are copied in `manual_signoff`, `adoption_signoff`, `adoption_requested`,
     `manual_choice`, `adoption_choice`, and `tracker_choice`.
   - Merge `adoption_signoff` and `adoption_requested` into one tri-state result: not an adoption
     question, malformed, or `(text, id)`. The `match asked, requested` in
     `hook._adoption_question` is non-exhaustive for `(tuple, False)`.
3. **A session `Pin` record in `scripts/harness/sessions.py`.**
   - `Session` gained five flat string fields, `start()` four keyword arguments, and `cli.py` a
     parallel `_SessionStart`.
   - `expected_base_commit` is written but never read. `readiness_verified_at` is used only for
     truthiness. `readiness_state` is compared as a string to `LogicalState.IN_PROGRESS.value`.
   - Replace these with a frozen `Pin(base_ref, base_commit, state: LogicalState, artifacts,
     verified_at)`, persisted as a nested `"pin"` record, and `Session.pin: Pin | None`.
   - Use `start(repo, item, workflow, pin=None)` and delete `_SessionStart`.
   - Keep reading the flat fields of sessions started by 0.3.0.
   - Decide whether `hook_runtime` should verify ancestry against the pinned base commit, or drop
     the field.
4. **`cli._startable` / `_feature_base` in `scripts/harness/cli.py`.**
   - `_startable` is six binds deep and indexes tuples (`found[0].key`, `base[1]`).
   - `_feature_base` strips `base_ref` four times.
   - Strip once, return early when no base is needed, and return the `Pin` from item 3.
5. **Typed adoption records in `scripts/harness/adoption.py`.**
   - Add `Assessment` and `Plan` frozen dataclasses with `from_record` / `to_record`, following the
     `sessions.Session` pattern.
   - These replace nested `report["source"]["fingerprint"]["digest"]` lookups and the defensive
     `str(found.get("digest", ""))` copies.
   - Fold the three separate approval checks (`plan_for_question`, `_write_pending_plan`,
     `materialize`) into `plan.approved(repo)`. `hook.handle_answer` reads the pinned plan the
     same way.
6. **One MCP process lifecycle in `scripts/integrations/transport.py`.**
   - `process_exchange` + `_session` (one-shot, still used by `harness doctor --tools` and the
     tests) and `_PersistentExchange` both build the `Popen` inline.
   - Make the one-shot path a `_PersistentExchange` that is closed after the call.
   - Delete the pass-through `persistent_exchange`.
   - Flatten the match-in-match in `_start`.
   - Fix the leak: `lru_cache(maxsize=16)` plus `atexit.register(self.close)` never closes an
     evicted exchange before exit. Close on eviction, or key an unbounded dict by
     `(command, args)`.
7. **Guard idiom.** Replace `match cond: case False: … case True: pass` with plain `if` in `hook.py`,
   `transport.py`, and `checks.py`. `main` had no occurrences; the house style destructures with
   `match` and guards with `if`.

8. **Let the user see which adoption plan they approve.** The bug review (L8) found that the
   **Approve adoption** question binds only the `HA-…` id. Re-running `harness adoption plan` keeps
   the id, and the digest is pinned when the question is asked. The plan shown in chat and the plan
   approved can therefore differ in destination or branch if the agent re-plans in between. Tracker
   trust and manual approvals work the same way. Require a short digest prefix in the question text
   so the user can compare it with the plan shown.

### Excluded

- Behaviour changes to rules, approvals, sessions, or adoption.
- The adoption-local cleanups already made before the 0.3.0 release: `sessions.checkout` reuse, one
  git runner, `_ensure` guards, a single `git log` for commits, and recording a settings failure
  in the assessment.

## Success Criteria

- [ ] `hook.py` has no `case _: pass` and one PostToolUse print; a question offering two approval
  kinds is denied.
- [ ] `Session` exposes one optional `Pin`; sessions written by 0.3.0 still load.
- [ ] `adoption.py` passes typed `Assessment` / `Plan` records; the approval check exists once.
- [ ] `transport.py` has one process lifecycle and closes evicted exchanges.
- [ ] All suites pass on Python 3.10 and 3.12; `hook.py`, `cli.py`, and `rules.py` are shorter
  than in 0.3.0.

## Areas / modules involved

- `plugins/monolithic-dev-harness/scripts/harness/hook.py`
- `plugins/monolithic-dev-harness/scripts/harness/questions.py`
- `plugins/monolithic-dev-harness/scripts/harness/sessions.py`
- `plugins/monolithic-dev-harness/scripts/harness/cli.py`
- `plugins/monolithic-dev-harness/scripts/harness/adoption.py`
- `plugins/monolithic-dev-harness/scripts/integrations/transport.py`
- `plugins/monolithic-dev-harness/scripts/hook_runtime.py`

## Original Description

"Its larger restructuring suggestions I'll leave for after the release; they don't change
behaviour." — "document those on the ai codex"
