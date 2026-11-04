---
title: Acceptance Fixture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-11-04
---

# Live-trial project fixture

This helper is for end-to-end tests of the harness only. The installed harness does not call it,
and regular project workflows do not depend on it.

`test-project-template/` is the starting project for these tests: a small Flutter task-list app with
its documentation and a `backlog/` of tickets that grow in difficulty. `DAY-001-task-counts.md` is
the usual simple test.

```sh
plugins/monolithic-dev-harness/bin/harness-python tools/project_fixture.py [--version X.Y.Z-rc.N] [--host HOST ...]
```

The helper:

1. Copies the template to the next unused `temp/test-NNN/` in this checkout, and commits it in a
   new Git repository as the starting point.
2. Finds the newest release candidate on GitHub, unless `--version` names one.
3. Downloads that release's `install.sh` and runs it with `--scope local --project <copy>` for each
   host (default: Claude Code and Codex), so the harness is installed for the copy only.
4. Prints the copy's path. The installer's output is in `temp/test-NNN-install.log`.

Bootstrapping and the workflow are the test itself; the `run-test-project` skill describes how to
run it, headless or interactive. `temp/` is ignored by Git; clear old copies by hand.
