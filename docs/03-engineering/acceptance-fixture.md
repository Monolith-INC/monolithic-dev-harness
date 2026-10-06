---
title: Acceptance Fixture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-02
---

# Live-trial project fixture

This helper is for disposable acceptance-test runs only. The installed harness does not call it,
and regular project workflows do not depend on it.

`test-project-template/` is the canonical starting project for human-run acceptance trials of the
harness. It is a small Flutter task-list app with project context, product intent, an unresolved
opportunity, current design notes, architecture, and test instructions.

For an app-based test run, pass a complete `.harness/settings.json` configuration to the test-only
factory in `tools/project_fixture.py`; `tools/test-project-config.example.json` is a starting
example. It validates the JSON against the harness settings schema,
creates a fresh copy, applies the configuration, initializes a selected local tracker through the
harness setup path, and returns `Ok(project_path)`. Missing, unreadable, malformed, and invalid
configurations return `Err` with a specific error. Starting a new fixture first removes abandoned
test-run copies created by this helper. Call `discard_test_project(project_path)` when the test ends.
This factory is not used by ordinary harness setup.

```python
from tools.project_fixture import create_test_project, discard_test_project
from core.result import Err, Ok

match create_test_project("/path/to/test-settings.json"):
    case Ok(project_path):
        # Point the test host at project_path, then discard it when the run ends.
        ...
    case Err(failure):
        print(failure.code, failure.message)
```

Never run the harness or edit files in the canonical template. Create a disposable, initialized
copy with the starting profile and per-run settings you need:

```bash
python3 scripts/acceptance_trial.py prepare
```

Use `--profile local-planning` to start with the local tracker, local source control, and
`docs/planning` for planning artifacts. A JSON file can override or add settings for that copy:

```bash
python3 scripts/acceptance_trial.py prepare --profile local-planning --settings /path/to/trial-settings.json
```

The command prints the ready project path. Each run receives a fresh copy, so setup does not need
to be repeated by hand. Point the selected host at that project for a trial. When finished, inspect
its results and remove only that copy with:

```bash
python3 scripts/acceptance_trial.py discard /path/printed/by/prepare
```

To launch a command-line trial with private temporary and preference storage, print the environment
for that copy and pass those values to the trial process:

```bash
python3 scripts/acceptance_trial.py environment /path/printed/by/prepare
```

The temporary directory is created with owner-only permissions for files created by the test
command. It does not relocate Codex's app-server socket: Codex uses a fixed host-level socket folder
under `/tmp`, independent of `TMPDIR` and `CODEX_HOME`. The preference directory keeps language and
other user choices inside the disposable trial. The runner also uses a disposable Codex home; when
a sign-in file is available, it links that file read-only and keeps logs, sessions, and caches in
the temporary copy.

For a command-line run, `run` manages the disposable copy automatically. It applies the environment,
starts the command in the project, deletes that run's copy when the command exits, and first removes
only abandoned copies created by earlier `run` invocations. When a Codex command is nested inside
another Codex shell sandbox, launch this test helper outside the outer sandbox; Codex's own
workspace-write sandbox remains enabled for the trial so normal local setup, planning artifacts,
and workflow checkpoints can be written. The scenario's stopping checkpoint still bounds the work.

```bash
python3 scripts/acceptance_trial.py run --profile local-planning -- codex exec --ignore-user-config <test-arguments>
```

This cleanup is limited to test-run folders with a valid ownership marker. It does not inspect or
remove projects used by regular harness workflows or copies created with `prepare`.

After a run, count explicit file-read and command events from its retained JSONL transcript with:

```bash
python3 scripts/acceptance_trial.py summarize /path/to/run-transcript.jsonl
```

The report distinguishes explicit file-read events from direct shell reads it can recognize, such as
`cat README.md`. Indirect reads through scripts or other commands may not be counted.

The helper does not install or remove the harness or start a host. Keep trial findings and defects
in `AI_Codex/Artifacts/live-trials/`; do not retain disposable working copies there.
