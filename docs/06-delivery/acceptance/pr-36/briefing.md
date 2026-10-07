---
title: PR 36 acceptance trial briefing
status: acceptance-pending
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-07
---

# Acceptance trial briefing

You are the project agent in a monolithic-dev-harness acceptance trial.

- PROJECT: `/tmp/monolithic-dev-harness-trial-hfex7n7v/project`.
- HARNESS UNDER TEST: source commit `3d723e3dda51097ff66723aba4631e34a4411d75`; installed
  integration must be verified against this revision before launch.
- HOST: Codex desktop, interactive. Parent model inherited; launch only after host choice is settled.
- SCENARIO: “I can see how many tasks I still need to do, but I also want to see how many I have
  finished. Show both counts on the task screen.”
- STARTING SETTINGS: local-planning; local tracker and SCM, artifacts in `docs/planning`.
- EXPECTED OBSERVATIONS: consolidated startup, correct conversation binding, grounded discovery,
  formally presented recorded decision with native controls or explicit graceful fallback.
- STOPPING CHECKPOINT: first grounded proposal/human decision. Do not implement.
- ALLOWED ACTIONS: local fixture setup, preference/session state, discovery artifacts and checkpoints.
  No remote writes, global host changes, canonical-template edits, or synthetic human approvals.
- EVIDENCE: this directory, outside the disposable project. Record actual calls, outputs and limits.

Work only in PROJECT. Use the verified installed harness's normal entry workflow; do not inspect
parent conclusions or harness implementation to predict findings. Relay human questions through
the parent and wait for actual answers. Do not spawn further agents. Report observed versus expected
behavior, artifacts, actual failures and unresolved decisions. Do not delete the fixture at a gate.

Launch is pending a desktop restart. The installed cache now matches all 366 checked source files,
but the running host may retain old hooks. After restart, verify the installation and launch the
trial. No test agent has been started and no acceptance result exists yet.
