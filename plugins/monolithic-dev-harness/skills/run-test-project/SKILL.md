---
name: run-test-project
description: "Launch a human-requested harness acceptance trial on a fresh disposable test-project copy, with an isolated runner, complete sub-agent briefing, and retained evidence. Use to test harness behavior, rather than run a normal project's unit tests."
---

# Run test project

This skill is owned and shipped by monolithic-dev-harness. A human can invoke
`$run-test-project` and specify the scenario, settings, host, and stopping checkpoint.
Accept `--interactive` and `--no-interactive` as skill invocation arguments:

- `$run-test-project --interactive`: prepare a fresh project and run with human participation.
- `$run-test-project --no-interactive`: launch the managed headless CLI trial.
- No mode argument: default to `--interactive`.

These arguments are interpreted by the coordinating agent, not passed to `project_fixture.py`,
`acceptance_trial.py`, or `codex exec`. If both appear, the last mode argument wins. Record the
resolved mode in the run inputs and sub-agent briefing. Keep that mode through fixes and reruns
unless the human changes it.
Create one fresh trial per invocation; do not launch a trial merely because this skill is discovered.
The parent coordinates preparation, evidence, and cleanup; a separately launched test agent exercises
the harness as a project agent. Preserve failed-run evidence before the parent fixes a defect.

## Parent briefing

Locate the harness **source checkout** containing `tools/project_fixture.py`,
`scripts/acceptance_trial.py`, `install.sh`, and `test-project-template/`. These test tools are not
shipped inside the installed plugin. If only an installed plugin is available, request the source
checkout path; do not substitute a hand-made fixture. Read that checkout's
`docs/03-engineering/acceptance-fixture.md` and the current tool help before launching.

Resolve these run inputs and write them to a new, uniquely named directory under
`AI_Codex/Artifacts/live-trials/` in the source checkout:

- Harness checkout path, revision and dirty-state summary; identify whether testing current source
  or an installed release. Preserve existing changes.
- Scenario and expected observable behavior; host; settings file or starting profile; stopping
  checkpoint; allowed writes; selected model, capability tier and reasoning effort.
- Absolute paths for `briefing.md`, `transcript.jsonl`, `stderr.log`, `result.md`, and `summary.json`.
  Keep evidence outside the disposable root, which will be deleted.

Defaults, when the human gives no overrides: current source, an interactive trial in the current
host with the human participating, local tracker and SCM,
`local-planning` profile, and a technical discovery trial for this request:
“I can see how many tasks I still need to do, but I also want to see how many I have finished.
Show both counts on the task screen.” Stop at the first grounded proposal/human decision checkpoint.
Allow the normal workflow to write local setup, preferences, session state, planning artifacts,
and checkpoints inside the disposable trial root, and retained evidence in its evidence directory.
Do not silently extend the trial into implementation. Stopping at discovery does not validate
implementation or later approval gates; do not fabricate human answers to gates.

## Test agent tier and reasoning

Prepare the fixture and filled briefing before starting the interactive trial. Launch a fresh agent in the current host with only the filled briefing. Give it the absolute
fixture path and require every file operation and command to target that project. A launcher-level
working-directory option is not required. Record shared-host isolation limitations in the evidence.
Relay its questions and checkpoints to the human and forward their answers; keep the trial available
for follow-up. Do not run `codex exec`, a background shell trial, or a noninteractive wrapper unless
the human selects `--no-interactive` or explicitly requests a headless/CLI run.
Do not create a separate chat unless requested.

Assign a general-purpose coding model of a tier compatible with the scenario, defaulting to the
economical coding tier: **gpt-6-luna with low reasoning effort** for Codex. Use the human's specified model,
tier and effort when provided. Pass those choices explicitly to the launcher and sub-agent briefing;
do not silently downgrade or reuse a review-only custom agent. Assume available models, tiers and
reasoning settings are compatible and have already been tested. Launch without compatibility checks
or gates. If execution fails, log the actual failure and effective settings, then diagnose and fix it.

## Prepare and launch

Use Python **3.12 or newer** for every fixture/setup command. Do not use bare `python3`, which may
resolve to Python 3.10. The harness's `plugins/monolithic-dev-harness/bin/harness-python` launcher
already selects the required interpreter; use its absolute path throughout and pass the selected
interpreter as `HARNESS_PYTHON` to child setup processes. A checkout virtual environment is another
option only when its actual interpreter is 3.12+. Do not install Python or change system defaults.

For the default interactive trial, call `create_test_project(configuration_file)` from
`tools/project_fixture.py` through that launcher, from the source checkout. Use a complete settings
JSON copied from `tools/test-project-config.example.json`, apply the requested overrides, and handle
the returned `Ok(project_path)` / `Err(failure)`. Save the settings and filled briefing in the evidence
directory. The factory creates a fresh numbered trial under `<checkout>/temp/test-000/project`
(or the next unused number), never a reused or manually relocated copy. Report the fresh project
path and launch the interactive project agent; do not turn preparation into a manual handoff.
Use the harness already installed in the current host; do not reinstall it globally for each trial.
Record any shared-host preference/session limitations without replacing the interactive run.

For `--no-interactive`, use the existing managed runner from the source checkout:

```sh
plugins/monolithic-dev-harness/bin/harness-python scripts/acceptance_trial.py run --profile local-planning -- codex exec --ignore-user-config --sandbox workspace-write --model gpt-6-luna -c 'model_reasoning_effort="low"' --json --output-last-message '<absolute-result-path>' - < '<absolute-briefing-path>' > '<absolute-transcript-path>' 2> '<absolute-stderr-path>'
```

Replace every placeholder and adapt only to verified current CLI options. The runner sets the child
working directory to the fresh project, isolates temporary storage, harness preferences and Codex
home, strips parent host-context variables, and discards the copy when the command exits. It removes
only marked abandoned `run` copies. Launch nested Codex outside the outer shell sandbox through the
host's supported escalation; retain the child's selected sandbox. Never bypass sandbox or hook trust
to make a trial succeed. Capture the launcher exit code even on failure.

The isolated Codex home initially has no installed harness. Before the test agent starts, the command
passed to `run` must perform the source installer step in that same environment and then execute the
agent. Use an absolute, per-run wrapper stored in the evidence directory, with the launch above's
`codex exec` portion as its final command. Invoke the installer with:

```sh
HARNESS_HOME='<owned-trial-root>/harness-install' HARNESS_BIN_DIR='<owned-trial-root>/bin' bash '<checkout>/install.sh' --host codex --source '<checkout>' --yes
```

Resolve the owned trial root from the runner's project working directory at runtime, and add its
`bin` directory to the child PATH. Set these installer variables only for the trial process; do not
modify global configuration. Verify the harness appears in `codex plugin list --json` using the same
isolated environment. Do not assume `--ignore-user-config` loads installed plugins: confirm availability
in the child transcript; if required plugin registration is suppressed, use the isolated trial config
instead and record the change. No user-global configuration should be read or rewritten for the trial.

For an app/interactive host, use `create_test_project(configuration_file)` from
`tools/project_fixture.py` with a **complete** settings JSON, starting from
`tools/test-project-config.example.json`. Handle its `Ok(project_path)` / `Err(failure)` result;
never proceed on `Err`. Keep the creating parent alive until cleanup. Alternatively, for a profile
or first-run setup trial, use `acceptance_trial.py prepare --profile local-planning` (or
`unconfigured` explicitly). CLI `--settings` merges overrides; the factory validates complete settings.
Use `acceptance_trial.py environment <project_path>` to obtain the isolated environment, then point
the host at that exact copy. A running desktop host may share preferences and plugin installation;
record that limitation and keep setup local rather than stopping or launching a headless replacement.
Retain artifacts before calling
`discard_test_project(project_path)` or `acceptance_trial.py discard <project_path>`.

Never run workflows in or edit `test-project-template/`. Never delete copies manually or uninstall
the user's harness. The fixture tools do not themselves install a plugin or launch a host.

## Sub-agent briefing template

Fill every field and pass this text as the initial prompt, without parent conversation history or
predicted findings. For the managed CLI runner, `PROJECT` is its current working directory; resolve
and report its absolute path before starting. For an app host, provide the returned absolute path.

```text
You are the project agent in a monolithic-dev-harness acceptance trial.
PROJECT: <fresh fixture path, or current working directory supplied by managed runner>
HARNESS UNDER TEST: <source revision/dirty state or installed release, expected plugin identity>
HOST / MODEL / CAPABILITY TIER / REASONING EFFORT: <assigned launch values>
PYTHON: <absolute Python 3.12+ interpreter selected by harness-python>
INTERACTION: <interactive by default; relay human questions through parent>
SCENARIO: <exact human request>
STARTING SETTINGS: <profile and overrides, or complete validated settings>
EXPECTED OBSERVATIONS: <behavior/checkpoints to observe, without prescribing findings>
STOPPING CHECKPOINT: <first human decision checkpoint by default>
ALLOWED ACTIONS: <normal local workflow setup, preferences, session state, planning artifacts and checkpoints inside the disposable trial root; evidence writes in EVIDENCE DESTINATION; implementation only when explicitly included in the scenario>
EVIDENCE DESTINATION: <absolute directory outside disposable project>

Work only in PROJECT. Verify its absolute path, harness availability and settings, then invoke the
installed harness's normal entry workflow for SCENARIO. Read project context and relevant source
as that workflow requires. Use the actual project and current harness instructions as evidence.
Complete onboarding without a session; select or start the work session only after setup is
verified and immediately before project work. Pass its ID to every subsequent workflow command.
Do not inspect the parent chat, past trial conclusions, or harness implementation to predict results.
Preserve starting files. Do not edit the canonical template, repair the harness, change global host
settings, perform remote tracker/SCM writes, push, or create a PR. Local project edits are allowed
only when ALLOWED ACTIONS explicitly includes them. Honor human gates; report a required decision
and wait for the human's answer through the parent in interactive mode. In noninteractive mode,
return the required decision as a blocked checkpoint and end the run; never simulate approval. Use PYTHON for
all Python commands; never fall back to bare python3. Do not spawn additional agents unless this scenario explicitly
tests delegation; assign any such agent a compatible tier and reasoning effort in its briefing.
Assume available models, tiers and reasoning settings are compatible and already tested. Do not
perform compatibility prechecks. Log actual failures and return the evidence to the parent for fixes.

Record observed workflow steps, actual tool calls, artifacts, failures and blocking decisions.
Return: project path; effective model/effort if exposed; plugin/settings verification; reached
checkpoint; observed versus expected behavior; changed files/artifact paths; checks with actual
results; unresolved decisions; and pass/fail/inconclusive with evidence. Distinguish host/environment
failures from harness behavior. Never claim an unexecuted check passed. At the checkpoint, return
your report and remain available for human follow-up in interactive mode. Do not delete the fixture
at a human checkpoint; the parent owns evidence retention and cleanup when the trial actually ends.
```

## Collect and finish

Wait for completion or the requested checkpoint. Preserve transcripts, stderr, final response and
any relevant project artifacts **before** cleanup; for `run`, arrange any project artifact export inside
the wrapper before it exits. On interruption, collect available evidence and report the partial run.
Summarize a retained Codex JSONL transcript with:

```sh
plugins/monolithic-dev-harness/bin/harness-python scripts/acceptance_trial.py summarize '<absolute-transcript-path>' > '<absolute-summary-path>'
```

Inspect actual evidence rather than trusting the agent's verdict alone. File-read counts are bounded
observations: indirect reads are not fully counted. Report scenario, harness revision, model/effort,
reached checkpoint, outcome, meaningful failures, evidence links and cleanup status. An observed
execution error is a failure, including missing required tooling, model access, SDK validation, or
approval capability. Use inconclusive only when evidence cannot establish the affected claim;
never downgrade an observed failed step to inconclusive.

When a failure occurs, retain its transcript and artifacts, log the failed step, exact error, impact
and diagnosis, then have the parent apply a focused fix within the authorized harness scope. Preserve
unrelated changes and record the fix and its validation. Re-run the same scenario on a fresh copy
after the fix, keeping both runs' evidence. Do not broaden the scenario or bypass human gates;
report any external dependency or permission that prevents the fix.
