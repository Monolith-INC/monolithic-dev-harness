---
title: Six-stage onboarding trial remediation
status: in-progress
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-09
---

# Six-stage onboarding trial remediation

## Purpose and boundary

Fix the planning-choice UI and reduce avoidable agent rediscovery in the six-stage onboarding
workflow, then prepare a clean live acceptance trial. The next trial starts from a fresh copy of
the test project and the ordinary harness entry point. This work does not implement DAY-001, write
to a remote tracker, deploy, or change global Codex settings.

## Evidence and findings

The relevant run is `temp/test-003/project`, described by
`docs/06-delivery/acceptance/six-stage-eef44fe/briefing.md`; its result is
`temp/test-003/project/docs/planning/acceptance-result.md`. The acceptance folder itself contains
only briefing/setup records. Do not use `six-stage-1571ba0` as evidence for this run.

- Discovery, planning, hardening, preparation, and confirmation completed. The decision record
  shows final approval `HD-53ae7702473a587f`; the workflow checkpoint remained at Confirmation and
  execution did not start.
- The plan, discovery/review documents, spec, local ticket draft, manifest, and result exist in the
  project fixture. The local ticket is a draft, not a materialized or published tracker item.
- The user reports that the method-selection UI disappeared after the method-selection step, the
  artifacts were not presented, and no final approval gate was visible. Tool-call success and a
  persisted answer do not prove that the host visibly rendered them. Treat the visibility outcome
  as failed/unverified until a clean live run demonstrates it.
- The chooser path has an instruction conflict. `bmad-build/step-02-plan.md` requires formal
  harness decisions, while `bmad-advanced-elicitation/SKILL.md` requires the agent to HALT on a
  five-method menu plus Reshuffle, List all, and Proceed. The harness gate catalog supports at
  most three options. This combination encourages an unstaged prose menu.
- After the user chose Proceed at 06:42:25, the workflow finished at 07:01:06 (18m41s). Activity
  included seven plan-check calls, reviewer/hardening work, reading artifact-generation guidance,
  CLI/path discovery for the manifest, producing and validating local planning artifacts, updating
  manifest digests, presenting review surfaces, final confirmation, and writing the result. This
  was a mixture of substantive work and repeated procedural rediscovery; the transcript alone
  does not establish how much wall time each activity consumed.
- The fixture was preconfigured with a project-local plugin copy, Codex configuration, harness
  settings, local tracker/artifact paths, and a trial briefing. It was not a clean copy with only a
  normal user request, so it could have introduced instruction and state conflicts.

## Implementation direction

1. Replace the prose-only elicitation menus with a native-first, paginated decision flow that
   respects the three-option limit. Keep contextual shortlist, full catalog, agent recommendations,
   reshuffle, multi-select, and Proceed behavior. Every fallback must preserve the same question
   and pending decision; never turn an unrelated lifecycle reply into an answer.
2. Make the six-stage storyboard the operational source of next actions. Skills should invoke
   named steps and consume saved artifacts instead of repeatedly rediscovering commands, paths,
   or whether to continue. Save meaningful progress at stage boundaries.
3. Ensure Confirmation presents the actual plan and companion artifacts through a visible host
   surface before one final bundle decision. State exactly what approval authorizes. A trial
   stopping at execution entry must not imply tracker writes or implementation were authorized.
4. Keep local tracker drafts, published tracker records, and execution distinct in wording and
   evidence. Save the result inside the fixture as part of the ordinary preparation flow.
5. Prepare a clean test-project copy for the next live run. Do not modify or erase existing
   acceptance evidence; do not seed session/decision state or a competing trial workflow.

## Acceptance criteria

- All elicitation choices use the decision UI when supported, with a same-decision fallback and no
  silent prose-menu substitution.
- The method chooser retains shortlist, full catalog, recommendations, reshuffle, selection, and
  Proceed while staying within the harness option limit.
- The agent proceeds from one saved stage to the next without the user prompting “what’s next” and
  without repeated command/path rediscovery where workflow instructions can provide it.
- Before confirmation, the user can inspect the complete plan and relevant companion artifacts;
  final approval is one decision bound to that unchanged bundle and its accurately described next
  actions.
- A clean fixture reaches Confirmation through normal harness entry, preserves project-local
  artifacts, and stops before execution when instructed.

## Verification sequence

Trace the elicitation contract and decision presentation code; add focused regression tests for
three-option pagination, multi-select, same-decision fallback, and native-menu instructions. Run
the focused harness tests and the repository's required suite. Then prepare a fresh test-project
copy and conduct one interactive acceptance run. Do not claim visible UI success from tool return
status or filesystem state alone.

## Scope exclusions

DAY-001 application code, tracker publication, remote writes, deployment, global host settings, and
changes to pre-existing acceptance fixtures.
