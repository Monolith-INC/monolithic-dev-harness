---
title: Onboarding friction audit
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-08
---

# Onboarding friction audit

Scope: runtime hooks, session and workflow lifecycle, setup readiness, decision transport,
integrated skills, catalog and documentation. Inventory covered 696 plugin files; recursive
search produced 347 relevant matches. Shared boundaries were inspected semantically. This is
evidence of that audit, not a claim that grep proves every possible failure absent.

| Failure or contradiction | Shared correction | Evidence |
| --- | --- | --- |
| Suspension still checked hook entry, settings/session context and protected records | Return allow before those vetoes; suspended observation is separate | Suspension and active-mode negative tests |
| Another pending decision prevented lifecycle controls | Separate human-control channel, independent of work decisions | Native suspend/resume regression leaves original decision untouched |
| A paused run or unanswered question prevented saving progress | Permit paused checkpoints and pending-safe progress controls; preserve scope isolation | Workflow and cross-session tests |
| Preparation inspected branches and required base/provider settings | Defer repository snapshot and remove readiness/proposal SCM requirements; filesystem root discovery | Setup, rendering and startup regressions |
| Prose questions silently replaced native controls | Require staged delivery or supported fallback at active stop boundary; detect Codex host | Stop, gate and host-detection tests |
| Depth was offered after plan drafting | Bilingual depth and method gates after discovery | Rendered-order and catalog tests |
| Multiple preparation approvals and scattered documents | One reviewed bundle; reading manifest with content hashes and triggers | Manifest and gate tests; updated stage contract |
| JSON/JSONL evidence was classified as application code | Narrow data exception in configured acceptance-evidence folder; explicit source patterns still win | Policy positives and source/symlink negatives |
| Literal quoted heredoc backticks became executed commands | Mask only non-expanding heredoc data for substitution scanning | Literal, executable-shell, mixed delimiter and carriage-return regressions |
| Repeated parsing made a 300-command hook exceed its existing time test | Bounded cache of pure parsing only, with independent returned lists | Original performance test passes at 2.3 seconds |

Unknown interpreters remain conservative: arbitrary inline Python can write files. Supported
readers and narrow progress commands are the recovery path; do not exempt every interpreter.
Changed pinned instructions, missing consequential inputs and unauthorized external actions remain
meaningful boundaries while checks are active. Suspension is the user's explicit release of those
checks, not an agent workaround.

The acceptance report was concurrently created by the test agent and was not edited. The shared
installed build and test fixture were not changed. Regression hooks are simulated host events;
they do not replace the genuine live native exchanges or establish end-to-end acceptance.
