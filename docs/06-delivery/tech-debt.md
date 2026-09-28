---
title: Tech debt
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-27
---

# Tech debt

Known gaps we chose to leave for now. Each entry says what the gap is, why it is open, the options
to close it, and when to revisit. Fix one on a `techdebt/…` branch and remove its entry.

## TD-1: A tracker can change between the walkthrough and the Trust question

- **Where:** onboarded trackers, trust by click (ADR-0009, decision 6).
- **What happens:** the harness pins the tracker folder's exact version when the **Trust** question
  is shown, not when the agent walks the user through the tracker. The folder under
  `.harness/trackers/` can be written by the agent, so the agent could change `adapter.py` or the
  staged values after the walkthrough and before asking. The user would then trust a version they
  were not shown.
- **Why it is open:** the user only ever sees what the agent relays, so no pin taken by the harness
  can prove what the user read. The earlier typed-digest line had the same limit. Closing the gap
  fully would stop the agent from staging trackers for the user.
- **Options:**
  - Make `.harness/trackers/` human-owned, so only a person can put a tracker there. Strongest, but
    the user copies the folder in by hand.
  - Record the version each time `harness tracker show` or `stage` prints the summary, and refuse
    a Trust question when the folder changed since that print. Catches edits after the summary, but
    not a summary printed again after an edit.
  - Show the file list and a short version code in the Trust question itself, so a change is visible
    to the user at the moment they click.
- **Risk today:** needs an agent working against the user; every other rule still applies to the
  trusted tracker's writes (approval windows, protected items).
- **Revisit:** before onboarded trackers are used outside the maintainers' own repositories.

## TD-2: The harness scripts and the backlog runtime import each other

- **Where:** `scripts/harness/local_artifacts.py` imports `orchestrator_core.project_config`, while
  `runtime/orchestrator_core/__init__.py` puts `scripts/` on the import path.
- **What happens:** the two layers depend on each other, so neither can be read or tested alone,
  and `project_config.load_project_config` exists only for this import.
- **Why it is open:** it predates the tracker work and touches the artifact-path logic every skill
  uses; changing it belongs in its own change.
- **Options:** move the artifacts-path lookup into `scripts/harness/settings.py` (it only reads
  `artifacts_path`) and have the runtime call it, or have the runtime's callers pass the resolved
  path in.
- **Revisit:** the next change to how skills resolve the artifacts path.

## TD-3: The capacity planner has its own result type

- **Where:** `runtime/orchestrator_core/providers/base.py` (`ProviderResult`), beside `core.result`.
- **What happens:** trackers answer with `Ok`/`Err`; the planner reads `ProviderResult`, so
  `ProviderResult.of` translates between the two, and warnings travel beside the value instead of in
  it.
- **Why it is open:** the planner, both capacity sources, and their tests speak `ProviderResult`;
  replacing it is a refactor of its own with no change in behaviour.
- **Options:** have the sources return `Result[(value, warnings)]` and the handlers `match` on it,
  then delete `ProviderResult`.
- **Revisit:** the next change to the capacity planner.
