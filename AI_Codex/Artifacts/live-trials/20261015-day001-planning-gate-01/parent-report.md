# DAY-001 planning-gate trial 01 — parent report

- **Scenario:** "I can see how many tasks I still need to do, but I also want to see how many I have
  finished. Show both counts on the task screen."
- **Harness:** current source `67970e9`, installed from source by the runner as plugin version
  0.6.2 in an isolated Codex home (path in the transcript:
  `codex-home/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.6.2`).
- **Host / model / effort:** Codex CLI `codex exec`, `gpt-6-luna`, low; `--sandbox workspace-write`;
  noninteractive (chosen by the human, because the Claude host has 0.5.2 installed).
- **Runner exit:** 0; about two minutes; fixture discarded by the runner after export
  (`project-artifacts.tar.gz`).

## Reached checkpoint

The first required human decision, `HD-a7673df5ad28fd09` (kind `required`, chat transport, scoped
to work session `WS-f5533728d428`): "Should I treat this work as standalone or part of an
initiative?" It came from BMad Build step 1 (`step-01-clarify-and-route.md`) after
`core.active_initiative` resolved empty. The agent presented it with `harness decision present`,
confirmed it pending with `harness decision status`, and stopped. No answer was simulated.

## Observed

- `harness begin` created the work session, saved the original request, and rendered the BMad
  discovery entry (`workflow.md`, step 1). Settings matched the `local-planning` profile.
- Reads: 11 simple shell reads (project docs, `backlog/DAY-001-task-counts.md`, the rendered BMad
  workflow and step 1, two harness references). No application source was read before the stop.
- Failed commands: 2, both from `harness knowledge catalog`/`find`: `.harness/knowledge/stores/project/catalog.json`
  is absent. Cause: the fixture is prepared by `scripts/acceptance_trial.py`, which writes settings,
  prepares the local tracker and `_bmad/`, but never runs the knowledge initialization that real
  `harness bootstrap` performs (`scripts/harness/bootstrap.py:321`). The workflow treated it as
  nonblocking, as its stage checks require. This is a trial-preparation gap, not harness behavior.
- One Codex host notice (`default_mode_request_user_input` under development); no effect observed.
- Project changes: only `_bmad/render/` (harness-generated). No source, tests, or planning files.
- Gate state at exit (`requirements-at-exit.json`): code-change gate not ready; only missing item
  `work_item_linked` (session names no work item). Correct for a run that stopped in discovery.

## What this establishes and what it does not

Established: the current source installs and starts; `harness begin` routes the exact request into
the BMad discovery steps; the first decision goes through the decision tool, is scoped to the work
session, and holds the run; nothing was implemented.

Not established: the planning gate itself. The run never reached a plan, Tasks, approval, linking,
or an attempted code edit, so no code-change refusal was exercised live. Verifying the complete
planning gate needs the human to answer each decision in turn, which a single noninteractive run
cannot do.

## Outcome

**Pass** for the stated checkpoint (first human decision, no implementation). **Inconclusive** for
the planning-gate claim, which this checkpoint does not reach.

## Follow-ups

1. Trial preparation: seed the knowledge store the way bootstrap does (call
   `harness.knowledge.initialize`), so discovery's knowledge ladder is exercised.
2. To verify the full gate: keep the fixture (`acceptance_trial.py prepare`, not `run`) and continue
   the same Codex session (`codex exec resume`) with each human answer relayed, through plan,
   Tasks, `implementation-confirm`, and the first attempted code edit; stop before implementation.
