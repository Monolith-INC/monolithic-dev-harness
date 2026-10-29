---
title: Acceptance Fixture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-29
---

# Live-trial project fixture

This helper is for disposable acceptance-test runs only. The installed harness does not call it,
and regular project workflows do not depend on it.

`test-project-template/` is the canonical starting project for human-run acceptance trials of the
harness. It is a small Flutter task-list app with project context, product intent, an unresolved
opportunity, current design notes, architecture, and test instructions.

`tools/project_fixture.py` prepares and drives a trial in three steps:

```bash
python3 tools/project_fixture.py create
```

Copies the template into `temp/test-NNN/project` (the next unused number) and installs the harness
into that copy for Claude Code and Codex: this checkout's source, or a published release with
`--version X.Y.Z`. `--host` picks other hosts; `--settings <file>` starts from a complete
`.harness/settings.json` (`tools/test-project-config.example.json` is an example) instead of a
first-run, unconfigured project. The install, the host configuration homes and the `harness`
command live in the trial folder beside the copy, so your own installs and host settings are never
touched. It prints the copy's path.

```bash
python3 tools/project_fixture.py run temp/test-000/project --runtime claude --briefing briefing.md
```

Starts the agent in the copy with the briefing as its first message. Headless, Claude Code may edit
files and run only the harness and read-only commands; Codex keeps its workspace sandbox. When the
harness waits for the human, `run` prints the question and exits with status 3. Answer it, as the
person or as the coordinating agent relaying the person's words, with:

```bash
python3 tools/project_fixture.py answer temp/test-000/project "Investigate first"
```

That resumes the same session with the reply as the user's next message, and stops again at the
next question. Add `--interactive` to `run` to open the host's own session in the copy instead,
where the person answers. The transcript accumulates in the trial folder's `transcript.jsonl`.

```bash
python3 tools/project_fixture.py discard temp/test-000/project
```

Removes the copy and its trial folder. The same steps are available from Python as
`create_test_project`, `start_run`, `answer` and `discard_test_project`.

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
