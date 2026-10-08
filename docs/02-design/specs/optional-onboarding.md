---
title: Optional onboarding and free mode
status: implementation
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-07
---

# Optional onboarding and free mode

Human direction: keep hook-only human answer recording and strict action governance. Make the
initial workflow officially onboarding, optional and restartable. Provide free mode for using
skills and guidance without sessions. Missing language capture must never stop work.

## Decision types

- Preference: safely defaultable or omittable; no workflow/write hold. Language is a preference.
- Required decision: the requested operation cannot correctly proceed without resolving it.
- Approval: context-bound permission for an action; existing authorization checks remain intact.

The catalog and saved decision identify the type. Existing language decisions are preferences;
unknown/older decisions remain required, and approval always wins over a preference classification.
Dismissal or supersession preserves evidence without creating an answer or permission. There is
still no agent-facing answer command. Type changes cannot weaken an approval.

## Onboarding controls and mode

`harness onboarding status|skip|dismiss|restart --repo <project>` manages only onboarding.
`harness mode status|free|structured --repo <project>` selects the user experience.
Skip and dismiss enter free mode; restart returns to structured onboarding. Existing sessions,
workflow progress, artifacts and approvals remain unchanged. No command requires a session.
Structured remains the default for existing installations; free mode is an explicit user choice.
Known onboarding prompts (`language`, `setup-confirm`, `next-step`, `starting-point`) are cancelled
when onboarding is skipped, dismissed or restarted. Cancellation is not an answer or an approval;
an abandoned settings proposal cannot be applied until a fresh review. Unknown required decisions
and approvals remain pending. Onboarding controls do not cancel the engineering workflow.

Setup review stores the proposed settings identity locally without applying settings. Cancelling
that review retains a separate marker, so an unrelated question cannot make the abandoned proposal
applicable again. Application requires a fresh human confirmation bound to the exact proposal and
source digests. Interrupted review projection is recovered before cancellation; repeated controls
are idempotent.

In free mode, the entry workflow supplies guidance without session creation, mandatory bootstrap,
tracker setup or language confirmation. Skills can be invoked directly, including ideation during
ongoing development. A skill's actual dependencies still matter when that operation is requested.
Free mode is not suspension, does not disable protected-state rules and cannot authorize external
writes or bypass required decisions. Returning to structured mode preserves saved progress.

Language order: captured project choice, valid saved user preference, English. Using a default does
not falsely record confirmation. A missing capture or skipped preference is not an error. Explicit
configuration corruption and genuine missing operation dependencies must remain distinguishable.

## Acceptance and documentation duty

Verify the exact failed case: legacy pending language, empty answer, no confirmed preference.
Work must proceed with English; no synthetic hook or rewritten answer is allowed. Verify onboarding
skip/dismiss/restart without a session and while an approval waits; approval stays pending and
protected actions still fail. Verify free entry without settings creates no session. Preserve
existing recorded-language behavior and normal structured execution.

Update entry/bootstrap guidance, decision protocol, bilingual catalog, main-flow specification,
diagram and meaningful-change checkpoints. Review security boundaries before commit. Keep previous
acceptance evidence, and do not claim live host acceptance from tests or source-only execution.
