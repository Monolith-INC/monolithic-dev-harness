---
title: ADR-0003 Human-only approval windows
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-06
---

# ADR-0003: Approval windows are opened only by the user's own prompt

## Status

Accepted

## Context

Gates G1, G2, and G4 need a person's approval before the agent writes to Azure DevOps. A hook
cannot see the conversation, and the agent must not be able to approve its own batch.

## Decision

The prompt hook (`UserPromptSubmit` / `beforeSubmitPrompt`) recognizes `approve HB-…` (or
`aprovo HB-…`) in the user's message and records an approval window under
`.harness/state/approvals/`. The `approval-required` rule allows tracker/SCM writes and `git push`
only while a window is open, and logs each write to it. The `human-owned` rule blocks the agent
from writing approval records. `harness revoke` closes windows early.

**Amended in 0.1.8: approval by click (Claude).** Typing a code was the least friendly step of the
process. In Claude the agent now asks one question with an `Approve` option, and the `PostToolUse`
hook on `AskUserQuestion` opens the window when the user picks it. The click is as human as a typed
prompt: the tool's answer comes from Claude's question picker, never from the agent. Two guards keep
it that way. The `PreToolUse` hook refuses a question that arrives with answers already filled in,
and it marks each question it lets through under `.harness/state/asked/` (human-owned). The
`PostToolUse` hook honours only an answer to a marked question, once, so a question that skipped the
check opens nothing. Typed `approve HB-…` stays, and is the only way in Cursor.

**Amended after 0.6.2 (unreleased): approvals tied to their context.** Approvals are asked
through the standard approval gates (ADR-0011), on every host, by click or typed reply. Each gate
says what its approval is tied to: the reviewed drafts or spec (by content digest), one existing
work item, one branch, or one pull request. Such an approval has **no time limit**. It holds until
the user revokes it, its work session stops or completes, or its context changes: an edited draft
or spec, or a write to a different item, branch, or pull request. Then the write is refused with a
note telling the agent to explain what changed and ask again. A general approval, tied to nothing
(a typed `approve HB-…`, or pausing tracker checks), keeps the short window. Asking the same gate
again for unchanged context returns the earlier answer instead of a new question. Answers are kept
in a human-owned history beside the decision record.

The decision itself is unchanged: only the user opens an approval, never the agent.

## Options Considered

- **Per-call confirmation by the host:** interrupts every write, and hosts differ.
- **Exact batch fingerprinting:** the hook cannot see the batch the agent showed the user.
- **Time-boxed window from the user's prompt (chosen):** simple, auditable, not forgeable by the
  agent.

## Consequences

### Positive

- The only path to a write goes through a real user message.
- Every write inside a window is logged with its tool and time.

### Trade-offs

- A general window covers any write for its duration, not only the batch that was shown.
- An approval tied to reviewed drafts covers that work session's tracker writes while the drafts are
  unchanged; the hook cannot match each write to one draft. Branch, item, and pull-request approvals
  are matched exactly.
- Tool output cannot open a window, but a user who pastes `approve HB-…` does.

## Host-specific Impact

Claude prints the recorded window back into the conversation; Cursor's prompt hook must answer
`{"continue": true}` and stays silent.

## Validation

`TestApprovalRequired` and `TestHumanOwned` in `tests/harness/test_hook_rules.py`;
`ApprovalByClickTests` in `tests/harness/test_questions.py`.

## References

- [../../02-design/workflows.md](../../02-design/workflows.md#approval-protocol)
