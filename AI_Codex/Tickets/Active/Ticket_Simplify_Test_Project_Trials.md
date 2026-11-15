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
- `test-project-template/ideas.md` and its copy `ideas.md`: the "First harness trial" section now
  describes the new process and no longer points at `AI_Codex/Artifacts/live-trials/`. Markdown
  lint and `scripts/check_repo.py` passed.

## Follow-up: one approval per artifact version

- Owner rule: show the full text of each artifact before its approval; a requested change comes
  back as the full updated text to approve again; nothing else asks.
- `refined.check_drafts` + `decision present --gate publish-items` refuse an unfinished Epic,
  Feature or Story draft in a work session; `create-entry` and `generate-work-item` refine first.
- `plan-checkpoint` is an approval (`binds = "artifacts"`, shown first); options Approve /
  Change or deepen / Approve and stop. Both approving options capture approval; previous labels
  have no compatibility mapping (Constitution, Article 11).
- Kept: the Story's implementation-plan approval and the Tasks' publish approval.
- Verification: full suite 1889 passed before the fixture update; `test_publish_once.py` 7 passed;
  `test_bound_approvals.py` 10 passed; ruff, Markdown lint, repo and version checks pass.
