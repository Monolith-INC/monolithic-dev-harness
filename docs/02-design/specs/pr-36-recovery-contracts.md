---
title: PR 36 recovery and host-binding contracts
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-07
---

# PR 36 recovery contracts

Scope: correct the four thermos findings without changing the approved F1–F6 product direction.

## Startup and resume

The application lifecycle owns checked resume. Onboarding and saved discovery verification must
succeed before a paused/stopped session becomes active. Both `begin` and explicit resume use this
operation, regardless of workflow stage. Startup selects the current session only after it has
successfully prepared the returned instructions. Creating work without selecting it is an internal
operation, not a new user choice. Failed startup may leave recoverable work, but must not silently
select it.

Unfinished startup records are excluded from implicit selection, including the sole-active-session
fallback. The atomic current-selection record also records which deferred sessions became eligible;
legacy sessions keep their existing behavior. A successful retry or deliberate explicit selection
can make recoverable work current.

## Decision and checkpoint recovery

A new question is validated before any checkpoint is persisted. Its pending decision is the durable
authority: it contains the expected old workflow and the intended review checkpoint until the
workflow projection completes. Decision-write failure leaves the workflow untouched. A checkpoint
write failure retains a pending question and recoverable projection; readers and answer capture
complete that projection before advancing. Recovery recognizes an already-applied projection,
never appends it twice, and refuses to overwrite workflow state that matches neither the old nor
intended state. Clearing recovery metadata after projection is idempotent. Recovery never creates
an answer or approval. Session-free and paused-workflow questions remain supported.

This is forward recovery, not an assertion that two filesystem replacements are atomic together.
Failure-injection tests must cover each persisted boundary, retry, and conflicting workflow state.

## Host binding

A trusted pre-tool event arms one exact `begin` invocation for one host conversation and tool-call
identity after the pending-decision guard permits it. Startup emits a fresh completion receipt only
after its validated result and current selection are saved. The trusted post-tool event must match
the armed command, invocation and completion receipt before switching the conversation binding.
Failed commands, ambiguous setup/session choices, missing identities, unarmed or replayed outputs,
and ordinary shell output cannot switch it. Receipt and arm records live in protected harness state.
A binding failure leaves recovery evidence and reports the problem; it must not silently appear
successful. Cursor supplies no conversation identity and continues using project-level selection.

Receipt consumption belongs to the same atomic record as the conversation binding and survives
later switches. Failure to clean up an arm record cannot make an already-consumed receipt reusable.
Selecting work with an existing question returns the complete saved presentation and completion
evidence, without creating another question or advancing its workflow. Recovery may reselect the
same pending scope; it must never leave an unanswered conversation for different work. An unbound
conversation may recover an explicitly selected pending scope only when no project-wide question
blocks it.

Tests cover real hook handlers for Codex and Claude payload fixtures, followed by native-question
presentation and human-answer capture in the selected session. Live-host acceptance remains a
separate requirement; fixtures do not establish compatibility with every installed host version.

## Structure and verification

CLI modules parse and render. Startup, checked lifecycle, durable review coordination and host
protocol live in focused modules. Preserve catalog wording, approval reuse, native fallback,
subagent depth and the pending-decision guard. Record each completed correction and its actual
verification in the checkpoint log. Run thermos again before considering the findings resolved.
