---
title: Acceptance Fixture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-02
---

# Live-trial project fixture

`test-project-template/` is the canonical starting project for human-run acceptance trials of the
harness. It is a small Flutter task-list app with project context, product intent, an unresolved
opportunity, current design notes, architecture, and test instructions.

Never run the harness or edit files in the canonical template. Create a disposable, initialized
copy with:

```bash
python3 scripts/acceptance_trial.py prepare
```

The command prints the copied project path. Point the selected host at that project for a trial.
When finished, inspect its results and remove only that copy with:

```bash
python3 scripts/acceptance_trial.py discard /path/printed/by/prepare
```

The helper does not install or remove the harness, start a host, or choose a tracker. Those choices
belong to the live-trial setup and will be documented separately. Keep trial findings and defects in
`AI_Codex/Artifacts/live-trials/`; do not retain disposable working copies there.
