---
title: "Simplify test-project trials"
type: ticket
date: 2026-11-04
branch: claude/clever-cannon-sql2ct (on codex/rc10-trial-fixes)
---

The owner's process: copy `test-project-template/` into the harness folder's `temp/`, install the
newest release candidate into that copy with the release's own `install.sh`, then run a headless or
interactive test: bootstrap, then the main workflow with a `backlog/` ticket (usually DAY-001).

## Ledger

- `tools/project_fixture.py` rewritten to do only that: copy to `temp/test-NNN/`, find the newest
  candidate (or `--version`), download its `install.sh`, run it with `--scope local`.
- Removed `scripts/acceptance_trial.py`, its tests and `tools/test-project-config.example.json`.
- `run-test-project` skill cut from 213 lines to the steps above.
- `docs/03-engineering/acceptance-fixture.md` rewritten; CHANGELOG Unreleased updated.
- `AI_Codex/Specs/2026-10-01-test-project-template-design.md` lifecycle tagged DEPRECATED.

## Verification

- `tests/harness/test_project_fixture.py`: 6 passed.
- Full suite `tests/run.sh`: 339 + 1880 passed, 2 skipped; installer checks passed.
- `scripts/check_repo.py`: passed.
- Live lookup of the newest candidate against GitHub returned `0.7.0-rc.10`.
- Not run: a real install from a downloaded release into a copy.
