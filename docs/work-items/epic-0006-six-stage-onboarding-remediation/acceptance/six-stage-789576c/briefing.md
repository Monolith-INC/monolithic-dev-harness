---
title: Six-stage live acceptance trial for 789576c
status: ready-for-human-run
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-09
---

# Live trial briefing

You are the project agent in a monolithic-dev-harness acceptance trial.

**PROJECT:** `/home/monolith/projects/monolithic-dev-harness/temp/test-002/project`

**HARNESS:** source commit `789576cb78d2e39cc997d433bf46681f6bc58eb0`, copied from the committed tree to this project's local Codex marketplace at `.agents/plugins/monolithic-dev-harness`. The project marketplace is `mdh-acceptance-789576c`; `.codex/config.toml` enables this project-scoped plugin. The plugin manifest says `0.6.2`; use the source commit and manifest digest in `setup.json` to identify the tested code. Do not update the user-wide plugin installation or configuration.

**HOST:** Codex Desktop, interactive, with the human participating. Record the model and reasoning effort shown by the host when the trial begins.

**SETTINGS:** local tracker and local SCM, `docs/planning` artifacts path. English is the user's established preference; continue in English without asking a language question.

**SCENARIO:** “I can see how many tasks I still need to do, but I also want to see how many I have finished. Show both counts on the task screen.”

**PURPOSE:** Exercise the normal harness entry workflow through Discovery, Planning, Hardening, Preparation and Confirmation. Observe whether the final confirmation is recorded as the Confirmation stage and whether archival trouble can be reported without blocking the workflow. Stop immediately at execution entry, before editing application source, tests, dependencies, building the feature, deploying or making remote writes.

## Run instructions

1. Open the exact PROJECT directory in a new Codex Desktop chat and trust the project if prompted. Confirm that the project-scoped `Monolithic Dev Harness acceptance 789576c` plugin is enabled. The `.codex/config.toml` setting is local to this project; do not change user-wide settings. If the project marketplace is not recognized, record the visible state and ask the parent for help rather than switching to the user-wide installation.
2. Start the harness normally for the exact SCENARIO. Follow the installed workflow and its actual questions. Use native controls first and its supported fallback if delivery fails. Do not fabricate answers, replay an answer into a different decision, bypass a hook, or inspect harness source to predict findings.
3. Complete the human's selected planning and review steps. The human owns every product choice and the single final bundle confirmation. Preserve the selected plan and the workflow's normal checkpoints.
4. At Confirmation, show the complete implementation plan and its referenced artifacts, request the one final confirmation, then stop at execution entry. Do not begin implementation even if the plan is approved.

## Evidence and allowed actions

Write the factual trial result to `docs/planning/acceptance-result.md` inside PROJECT. Include frontmatter (`title`, `status`, `owner`, `last_reviewed`), the actual choices and decision IDs/statuses, relevant command outcomes, reached stage, artifact paths and SHA-256 digests, failures, and observed-versus-expected behavior. A result and artifact manifest inside the project are the evidence of record. Keep the complete host transcript in its original host store; do not copy it into the repository or another workspace. If transcript access or export is unavailable or rejected, record that limitation in the result. Export failure alone is not a workflow blocker and must never be bypassed. Do not claim evidence was saved unless the project-local file exists and was checked.

Allowed changes are local harness setup/preferences/state, planning documents and checkpoints, local tracker drafts, and the acceptance result inside PROJECT. Do not change the canonical template, global host settings, or any other project. Do not delete or discard this fixture at the checkpoint. Report the exact PROJECT path and remain available for follow-up.

Expected end state: final approval, if given, is recorded; the workflow checkpoint is `confirmation` before entering `execution`; the trial stops at execution entry; `acceptance-result.md` and the plan artifacts remain in PROJECT. This tests this run only and does not establish implementation quality or release readiness.
