---
title: Recoverable Session Startup Implementation Plan
type: implementation-plan
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-26
---

# Recoverable Session Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Use checkbox steps to record progress. This document is a draft for review; it does not authorize implementation, delegation, installation, or a live run.

**Goal:** Resolve the harness work session once at agent-session entry, with an explicit human choice to continue existing work or start new work, and preserve a usable recovery path whenever session entry or continuation cannot proceed.

**Architecture:** Introduce a host-neutral session-entry state machine and a small protected persistence boundary. Host startup hooks load its context; human session choices use a control channel independent of pending work decisions. The existing work-session, workflow, and approval modules remain authoritative for their respective records.

**Tech Stack:** Python 3.12+, frozen dataclasses, exhaustive `match`, the existing `core.result.Result` combinators, JSON state, TOML question catalog, and existing host adapters. No new dependency or vault installation.

**Spec:** The requirements below capture the owner's instructions in this conversation. The prior-art section records the inspected implementations. Implementation approval remains outstanding.

**Status:** Draft, 2026-10-26.

## Requirements and global constraints

1. "The check is done once, on the first interaction." Prefer the agent-session startup lifecycle event. Do not discover sessions or reopen the selection menu on every prompt, tool call, or workflow step.
2. When an existing session is found, ask whether to continue it or create a new session. Do not automatically continue an exact request match.
3. Continuing makes the chosen harness session active, links the current agent session to it, and restores its saved work and pending question.
4. Starting new requires presenting the available dispositions for the previous session and executing the user's choice first.
5. "There can be no condition, save for catastrophic system failure or similar, that halts the harness without a clear path to recovery." Blocked work must retain an executable recovery control or a precise external repair instruction when the environment prevents execution.
6. Only genuine human input selects a session or disposition. Selection, delivery, retry, silence, timeout, and default buttons grant no product or write approval.
7. Session entry must work before bootstrap is complete and without a tracker, Git branch, or successful workflow rendering.
8. Preserve original requests, checkpoint history, decisions, reviewed digests, unrelated sessions, project settings, and unrelated working-tree changes.
9. Use functional transformations and `Result`; isolate filesystem effects. Do not introduce imperative `if/else` blocks, mutable state in the domain model, or void-returning domain functions.
10. Keep verification scoped to this change. No tests or project-wide validations are authorized by the current request. Do not run them during planning or silently add them to execution. The owner performs the live rerun.

## Proposed implementation decisions for review

These details are proposals, not previously approved owner decisions:

- Use a **harness work session** for durable work and an **agent session** for the host's chat/runtime identity. One work session can outlive several agent sessions.
- Scope the one-time entry record to resolved project root, host, and native root-agent session ID. A new chat or fork starts a new entry; duplicate startup, resume, and compaction notifications for that same identity retain its completed selection.
- Startup may inspect and report existing work before a request exists. It must not create a new work session, resume work, or ask an unrelated chat to choose work before the first harness request. Save that original request when it arrives.
- Offer **Pause for later**, **Stop and keep history**, and **Cancel starting new** for the previous session. Reuse existing pause/stop semantics; stopped work remains recoverable, and neither choice means successfully completed. Never silently delete or purge it.
- When several sessions exist, show their request, work item, status, checkpoint, and pending question; let the user choose which session to continue or replace. Do not silently affect all active sessions.
- Keep completed sessions as readable history. Ordinary continuation targets active, paused, or stopped sessions; starting follow-up work from completed history creates a new linked session.
- Treat project-wide unfinished setup as an explicit **Interrupted project setup** candidate when no work-session owner is recorded. Ask where it belongs; do not guess from the newest session or current pointer.
- Implement native `SessionStart` entry for Codex and Claude. Other installed hosts use their existing first harness-entry path unless their startup event and identity are already supported and documented. Do not invent host capability or widen this change into adapter qualification.
- Replace the temporary unconditional fallback-origin rebinding with a handoff authorized by the user's session-continuation choice. Transport fallback itself must not transfer session ownership.

## Current behavior and affected boundaries

| Boundary | Current behavior | Required change |
| --- | --- | --- |
| `harness/startup.py` | Setup must be ready before session selection; matching active work can continue automatically. | Entry selection precedes setup-dependent execution; use the selected durable session. |
| `harness/work_sessions.py` | Stores independent sessions; `current()` can fall back to another active session. | Retain storage/lifecycle; agent-bound work must not silently adopt a different project's current session. |
| `harness/work_lifecycle.py` | Choosing/resuming invokes discovery verification. | Separate selecting/activating local work from permission to advance a stale or unverified workflow. |
| `host_adapters/work_session_context.py` | Binds native conversations; pending decisions restrict recovery switching. | Consume the explicit entry result and keep recovery available even if the old binding is invalid. |
| `harness/hook.py` | Pending-decision checks can reject entry; `startup` is post-tool capture for `begin`. | Add a distinct `session-start` event and an independent session-control path; preserve existing receipt capture. |
| `harness/harness_controls.py` | Suspend/resume/free controls already have independent human capture. | Reuse its separation and capture patterns for session controls, without changing work decisions. |
| `harness/decisions.py`, `cli_workflow.py` | The temporary fix lets fallback rewrite `native_session_id`. | Move ownership transfer into authorized continuation; fallback only changes delivery. |

Paths under `harness/` and `host_adapters/` below are relative to `plugins/monolithic-dev-harness/scripts/`. Paths under `hooks/`, `config/`, `skills/`, and `references/` are relative to `plugins/monolithic-dev-harness/`. Paths under `docs/` are repository-relative.

## State and public contract

Create `harness/session_entry.py` for the pure model and `harness/session_entry_store.py` for persistence and lifecycle effects. Create `host_adapters/session_entry.py` for trusted identity, event normalization, and question capture. Keep `hook.py` integration thin.

Define frozen records in `harness/session_entry.py`:

- `EntryIdentity(project: str, host: str, agent_session_id: str)`.
- `Candidate(id: str, kind: str, request: str, status: str, work_item: str, checkpoint: str, pending_question: str, digest: str)`; `kind` is `work_session` or `interrupted_setup`.
- `RecoveryAction(operation: str, command: tuple[str, ...], explanation: str)`; operations are `present`, `retry`, `back`, and `repair_storage`.
- `EntryRecord`: version, identity, revision, phase, original request, frozen candidates, chosen candidate, pending control identity, captured choice evidence, transition ID, selected work-session ID, and recovery actions. Optional fields use explicit tagged variants where absence changes behavior.
- `EntryEvent`: request received, human continue, human start-new, human candidate selection, human disposition, human preserve-and-isolate, retry, back, and transition completed.
- `EntryPlan`: next record plus a tuple of typed local effects. Its phase is `awaiting_request`, `choose_session`, `choose_candidate`, `choose_disposition`, `applying`, `ready`, or `recoverable_error`.

Interfaces:

| Module | Interface | Responsibility |
| --- | --- | --- |
| `harness/session_entry.py` | `reduce_entry(record: EntryRecord, event: EntryEvent) -> Result[EntryPlan]` | Pure, exhaustive transition planning. |
| `harness/session_entry_store.py` | `load_entry(identity: EntryIdentity) -> Result[EntryRecord]` | Read an entry; distinguish absent, malformed, and unavailable storage. |
| same | `start_entry(identity: EntryIdentity, request: str) -> Result[EntryRecord]` | Return an existing entry unchanged; discover candidates only when absent. |
| same | `apply_entry(identity: EntryIdentity, event: EntryEvent) -> Result[EntryRecord]` | Validate recorded human evidence, journal and apply local effects, then publish the binding. |
| same | `recover_entry(identity: EntryIdentity, operation: str) -> Result[EntryRecord]` | Retry/back without an agent-supplied answer or implicit disposition. |
| `host_adapters/session_entry.py` | `observe_start(repo: Path, host: str, payload: dict) -> Result[dict]` | Normalize trusted root identity and produce startup context. |
| same | `capture_choice(repo: Path, host: str, payload: dict) -> Result[EntryRecord]` | Match genuine prompt/native-answer evidence to exactly one entry control. |
| same | `recovery_command(command: str, cwd: Path, repo: Path) -> bool` | Recognize only exact, same-project session-entry controls. |

Store entry records at `.harness/state/session-entry/<host>/<sha256-native-id>/entry.json`; retain transitions and prior bytes under that entry's `transitions/`. Use atomic JSON writes, monotonic revisions, and an entry/project transition lock at the persistence boundary. Do not replace `work_sessions`, workflow history, or existing host binding records.

Expose `harness session-entry status|present|retry|back --repo <project>`. Identity comes from observed host context and a matched invocation, not agent-supplied identity flags. There is no agent-facing `answer`, `approve`, `continue`, or disposition setter. The root's genuine answer hook applies the prepared action. Existing explicit work-session commands may operate after entry, but cannot bypass its pending human selection.

Every non-ready entry response contains its state, a plain explanation, and at least one concrete recovery action. Explanations never tell the agent merely to "stop and inspect".

## Review focus

1. The original bug: project-wide setup decision owned by an earlier native session, with the current chat answering a re-presented menu.
2. Duplicate startup/resume/compaction events and lost post-tool output: no repeated selection or duplicate work-session creation.
3. Pending work decision plus a session-control numeric reply: consume it only as the session choice; preserve the work decision unanswered.
4. A malformed session, stale candidate, or write interruption must not prevent recovering healthy work or choosing new work.
5. Concurrent root chats and native children must not overwrite a binding, transfer approvals, or apply another chat's answer.

## Task 1: Define entry transitions and documentation contract

**Files:** Create `harness/session_entry.py`; create `docs/01-architecture/decisions/ADR-0013-recoverable-session-entry.md`; update `plugins/monolithic-dev-harness/references/human-decisions.md` and `references/codex-runtime.md`.

**Consumes:** Existing `core.result`, work-session statuses, workflow checkpoint summaries, and the requirements in this plan.

**Produces:** The records, phases, `reduce_entry` interface, and recovery action shape above.

- [ ] Specify the one-time entry boundary, root-only session ownership, human-only choice, and the distinction between activation and workflow advancement.
- [ ] Define deterministic transitions for no existing work, one/multiple candidates, continue, new/disposition, cancel, and repeated entry events. No existing candidate means create work only after a meaningful original request arrives.
- [ ] Every error variant returns a recovery action; back/cancel preserves records and the original request. Suspended/free mode remains an explicit owner choice and does not silently resume structured work.
- [ ] Record scenario evidence expectations: exact-request matches still ask; elapsed time and branch changes never automatically close a work session; repeated events retain the selected session.
- [ ] Review the transition table against requirements 1–10. Check only this module's syntax/lint and the edited documentation links; run no tests.

## Task 2: Implement durable selection and interruption recovery

**Files:** Create `harness/session_entry_store.py`; modify `harness/work_sessions.py`, `work_lifecycle.py`, `startup_receipts.py`, `rules.py`, and `host_adapters/work_session_context.py` only at selection/persistence/protected-record boundaries.

**Consumes:** Task 1's `EntryPlan` and typed effects.

**Produces:** `load_entry`, `start_entry`, `apply_entry`, and `recover_entry`; durable transaction receipts consumed by trusted host binding.

- [ ] Discover candidates without requiring valid settings, Git, tracker, discovery rendering, or a usable old host binding. Retain malformed records as visible problems rather than failing the entire healthy candidate list.
- [ ] Revalidate candidate digests immediately before application. A changed candidate returns an updated control for review; never apply the old reply to new state.
- [ ] Journal each captured human action with identity, source/target IDs, expected revisions/digests, local before-images, and an idempotency key. Use atomic writes and serialize competing local transitions.
- [ ] Protect the new entry, question, and transition records using the existing protected-state rules. Extend the direct internal-runtime invocation restrictions to the new effectful modules; an agent cannot forge a receipt by importing the store or writing its JSON. Only trusted hook capture and verified local lifecycle effects may publish selection authority.
- [ ] Continue: activate the chosen session and bind this agent to it without recreating its workflow. A discovery mismatch yields a concrete recovery state while preserving the selected work and checkpoint.
- [ ] New: apply only the selected previous session's pause/stop disposition, retain its workflow/decisions, create one new session, then publish the pointer and host binding. New work receives no old approvals. Cancel creates nothing and changes no work status.
- [ ] Interrupted transaction: resume missing idempotent effects from its receipt. Until commit, guards continue using the last committed binding and prevent ordinary writes; an intermediate pointer is never treated as authority. Conflicts preserve both versions and offer back/review, rather than overwriting concurrent work.
- [ ] For unreadable records, offer retry or a human-confirmed preserve-and-isolate action before new work. Resolve all archive inputs beneath the exact project state root and reject symlink escapes. Preserve exact bytes under the recovery archive and remove only the explicitly selected unusable binding from active selection; never mark corrupted work complete.
- [ ] If storage cannot be read or written, return the exact affected path and the external action needed to restore access or a backup, followed by `session-entry retry`. Do not manufacture a successful selection or authorize work using an in-memory substitute.
- [ ] Scope checks to these changed files and verify by inspection that no fall-through selects another active session after binding failure. No tests.

## Task 3: Wire agent startup once, independently of work blockers

**Files:** Create `host_adapters/session_entry.py`; modify `harness/hook.py`, `startup.py`, `cli_workflow.py`, `cli.py`, `host_adapters/startup_context.py`, `hooks/codex.hooks.json`, and `hooks/hooks.json`. Update `host_adapters/installation_project.py` only if its existing manifest translation needs adjustment.

**Consumes:** Task 2's entry and transaction receipts.

**Produces:** `session-start` hook dispatch, session-entry CLI controls, and the first-harness-interaction entry path.

- [ ] Add a distinct `--event session-start`; do not repurpose existing `--event startup`, which verifies completed `begin` calls. Add Codex/Claude `SessionStart` wiring using native event output shapes.
- [ ] Normalize project/host/root identity through the host adapter. Child events inherit their assigned work scope and never initiate a menu or select a parent work session.
- [ ] For an existing entry, inject its saved context and next step without rediscovering candidates or requesting another selection. Compaction/resume with the same identity preserves it. A fork/new identity gets its own entry.
- [ ] Where no startup event ran, invoke the same initialization once on the first actual harness entry using its trusted host identity. Ordinary prompts/tool calls do not perform candidate discovery. Missing trustworthy identity reports a concrete host-reload or supported-host recovery action; it must not invent a shared identity.
- [ ] Let `begin` consume the completed entry selection before bootstrap/discovery. Remove the automatic `continue_active` selection route for a new agent entry; explicit `--session`/`--new` cannot stand in for missing human entry evidence.
- [ ] Permit exact same-project session-entry controls before old work-session-context, onboarding, and pending-work-decision checks. Retain protected-state, project-path, native-child, and effect-scope restrictions. A compound command containing a recovery command is not exempt.
- [ ] Retain the current root/work binding for ordinary enforcement after entry; this task does not disable existing action approval checks.
- [ ] Inspect generated Codex and Claude project assets using the existing pure asset builders only. Check that `SessionStart` and post-`begin` hooks both remain present; no install or project-wide doctor run.

## Task 4: Capture session choices independently of work questions

**Files:** Modify `host_adapters/session_entry.py`, `harness/harness_controls.py`, `harness/hook.py`, `harness/cli_workflow.py`, and `config/gates.toml`.

**Consumes:** Entry candidates, revision, prepared control identity, and the existing host question transport contract.

**Produces:** `capture_choice` and localized session-entry presentations that preserve pending work questions.

- [ ] Add English/pt-BR catalog copy for continue/new/cancel, candidate selection, pause/stop/cancel disposition, and retry/preserve-and-isolate/back for an unreadable record. Treat these as lifecycle choices with no product-write approval, not optional preferences with a silent default.
- [ ] Show request/work-item/status/checkpoint/pending-question summaries before asking. For multiple candidates, page two candidates plus a More option, keeping at most three choices. A separate `back` control returns to the prior page; use the same candidate IDs and frozen revision in typed fallback.
- [ ] Store prepared session controls separately from `.harness/state/decision.json` and session work decisions. Reuse the existing independent lifecycle-control architecture, not a second competing answer parser.
- [ ] Match native replies by prepared question/call identity and typed replies by the current trusted conversation's prepared lifecycle menu. Consume a session-control answer before examining an ordinary work decision. Never use the same `1` for both.
- [ ] Use native presentation only when the actual host contract permits that decision class. Otherwise present the exact typed menu. Delivery acknowledgement, picker dismissal, timeout, and a preselected option never apply a choice.
- [ ] A failed presentation returns `session-entry present` for that same control with the next permitted transport. Explicit retry re-presents saved state; it does not repeat initial discovery or create a replacement question.
- [ ] Replace each affected bare rejection with the exact same-project recovery command and what it does. Inspect pending-context, invalid-binding, interrupted-setup, and stale-render denial paths; do not audit unrelated project behavior.
- [ ] Check only changed code/catalog syntax and formatting. No tests or synthetic hook-answer execution.

## Task 5: Restore saved questions through an authorized handoff

**Files:** Modify `harness/decisions.py`, `harness/setup_reviews.py`, `harness/startup.py`, `harness/workflow.py`, `harness/hook.py`, `harness/cli_workflow.py`, and the two new session-entry modules as needed for their defined responsibilities.

**Consumes:** A committed Continue selection and its genuine human evidence from Tasks 2–4.

**Produces:** Resume of the selected checkpoint and a question-delivery handoff that cannot be obtained by merely invoking fallback.

- [ ] On Continue, preserve the pending decision ID, wording, labels/details, type, scope, reviewed digests, and prior delivery history. Move its active delivery origin to the selected root conversation only through the committed entry transition; retire stale presentation bindings without deleting their evidence.
- [ ] Re-present the original unresolved work question after selection. A session-selection answer never becomes its answer. Old-conversation controls cannot resolve it after the handoff.
- [ ] Remove `_fallback_origin` and its unconditional CLI `CODEX_THREAD_ID` transfer once the authorized path is in place. Keep ordinary transport fallback and human-only prompt/answer capture.
- [ ] Handle project-wide interrupted setup explicitly: retain its original request, proposal/source digests, asked markers, workflow checkpoint, and decision together. Continue adopts that bundle into the selected work scope with a durable migration receipt; new work archives it only after the user explicitly chooses its disposition. Project settings stay project-wide and are not reset.
- [ ] When ownership is ambiguous, present the interrupted-setup candidate independently instead of attaching it to the newest session. New work must not accidentally inherit its project-wide pending blocker or approval.
- [ ] Preserve already-recorded answers while applying existing digest/window/session validity rules. Session selection creates no approval window and does not validate changed artifacts.
- [ ] Corrupt/missing checkpoint instructions return a repair/back/new path; never silently restart the workflow or claim an unverified checkpoint completed.
- [ ] Inspect the exact Oct 25 failure path against the new sequence: old native owner → entry Continue → committed binding → original menu → genuine typed reply → recorded decision → next work step. Do not run a live answer or tests on the owner's behalf.

## Task 6: Finish documentation and prepare scoped acceptance

**Files:** Update `plugins/monolithic-dev-harness/skills/harness/SKILL.md`, `skills/bootstrap/SKILL.md`, `references/human-decisions.md`, `references/codex-runtime.md`, and ADR-0013; create `docs/work-items/epic-0008-codex-host-adapter/acceptance/codex-adapter/session-entry-live-checklist.md`.

**Consumes:** The final entry interfaces, allowed recovery commands, and capture/transaction semantics.

**Produces:** Consistent operational instructions and a bounded owner-run acceptance checklist.

- [ ] Replace superseded auto-selection and fallback-transfer instructions. Describe selecting a work session once, explicit prior-session disposition, activation versus advancement, and recovery before setup. Do not retain conflicting obsolete guidance.
- [ ] Document the lifecycle sources and host coverage actually implemented. Do not claim native startup support or live qualification from manifest presence alone.
- [ ] Run only file-scoped syntax, lint/format, JSON/TOML parse, documentation-link, and diff-whitespace checks for files changed by this implementation. Record exact paths and outcomes; no test suite, project-wide validator, broad doctor, or unrelated acceptance workflow.
- [ ] Prepare the following live scenarios for the owner; each must have its expected visible menu, persisted session/checkpoint result, and recovery path:

| Scenario | Expected result |
| --- | --- |
| No previous work; startup has no request yet | Orientation only; the first meaningful harness request creates exactly one session. |
| Existing active session, including exact request match | Continue/new choice appears once; no automatic reuse. |
| Paused/stopped session → Continue | Session becomes active; saved checkpoint and pending work question return. |
| Start new → Pause / Stop / Cancel | Chosen disposition is recorded first; exactly one new session, or none on Cancel. |
| Old native owner with project-wide setup decision | Continue authorizes handoff; a later answer to the original menu records correctly. |
| Pending work question plus session-menu numeric reply | Only the lifecycle menu is answered; work question stays pending. |
| Repeated startup, same-chat resume, compaction, or delivery retry | No duplicate discovery/menu/session; saved selection remains. |
| Fork or another root chat in the same project | Independent entry; no accidental replacement of another chat's binding. |
| Stale/corrupt candidate, changed digest, or interrupted transition | Concrete retry/back/repair choice; preserved evidence; no duplicate session or partial authority. |
| Incomplete/paused bootstrap or unavailable discovery/tracker | Session controls remain available; ordinary advancement reports its own precise repair path. |
| Native UI unavailable, dismissed, or delayed | Same prepared typed control is usable; delivery never counts as an answer. |
| Child attempts to select or answer for the root | No lifecycle mutation; clear instruction to return the need to the root. |
| Agent tries to write entry JSON or invoke the internal store directly | No forged selection/answer; the exact supported session-entry controls remain available. |

- [ ] State that concurrency/interruption behavior has only static review evidence until exercised. The no-tests restriction limits confidence; do not mark unexecuted scenarios passed.
- [ ] Stop with the implementation ready for owner review/live acceptance. This plan does not authorize another `--purge`, installation, release, merge, or live run. If the owner later requests a fresh fixture install, back up the exact target and use the existing scoped installer.

## Completion criteria

- The owner reviews this draft and its proposed choices before implementation.
- Implemented entry occurs once per agent-session/project identity and never automatically resumes an existing work session.
- Continue and new/disposition flows preserve work and only act on captured human choices.
- The old fallback-only workaround is replaced, not left as a second ownership-transfer path.
- Every touched blocked state exposes a recovery action that is allowed in that state; unrecoverable storage/access conditions explain the external repair and retry command.
- Scoped static checks pass. No tests or project-wide validations run under the current restriction.
- The owner reruns the scoped live scenarios; live success is reported only after that evidence exists.

## Prior art and sources inspected

- [Agent Continuity startup hook](https://github.com/Monolith-INC/agent-continuity/blob/e744d78443e34624b54e325cd9ee8756a55a192f/hooks/scripts/bootstrap.sh): orientation injection on SessionStart.
- [Agent Continuity workspace protocol](https://github.com/Monolith-INC/agent-continuity/blob/e744d78443e34624b54e325cd9ee8756a55a192f/skills/init-workspace/SKILL.md): recent records, linked history, checkpoints, pre-operation snapshots. Reuse these ideas; do not copy its automatic predecessor closure into the user's explicit-choice flow.
- [Original workflow session gate](https://github.com/Monolith-INC/codex-workflows-plugin/blob/2cca013bb19192310338262802c64db20ec6579c/scripts/policy/session_gate.py): historical branch/age-based continuation. Do not import its repeated scanning or eight-hour expiration policy.
- [Codex SessionStart contract](https://learn.chatgpt.com/docs/hooks#sessionstart), consulted 2026-10-26: startup/resume/clear/compact/fork sources and context injection. Duplicate lifecycle notifications do not authorize repeating session selection.
- Current local startup, work-session lifecycle, independent harness controls, host-binding receipts, decision recovery, and native installation-manifest translation listed in the tasks above.
