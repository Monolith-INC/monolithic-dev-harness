---
title: Testing
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
---

# Testing

## Purpose

What the automated suites prove, what they do not, and which additional gates cover the gap.

## Prerequisites

A virtual environment with `pytest` (see [development.md](development.md)).

## Authoritative Source Files

| Suite | Path | Covers |
| --- | --- | --- |
| Backlog | `plugins/monolithic-dev-harness/tests/backlog/` | artifact validation, estimation, capacity, providers, skill layout, plain-language integration |
| Core | `plugins/monolithic-dev-harness/tests/core/` | `Ok`/`Err` values; the standard-library schema checker |
| Integrations | `plugins/monolithic-dev-harness/tests/integrations/` | the registry and tracker contract, each shipped adapter against its provider's reply shapes, SCM adapters, the transport against a real server process, the gateway, trust, onboarding |
| Delivery | `plugins/monolithic-dev-harness/tests/delivery/` | workflow policy runtime with real sessions and the local tracker, git guards, orchestrator contracts and reducers, manifests |
| Harness | `plugins/monolithic-dev-harness/tests/harness/` | harness rules through the real hook entry point for Claude Code, Cursor, and Codex; settings; sessions and `harness session`; bootstrap; knowledge |

## Generated Files

Tests create throwaway git repositories under the system temp directory and remove them.

## Development Workflow

```bash
PYTHON=.venv/bin/python plugins/monolithic-dev-harness/tests/run.sh
```

`tests/run.sh` runs the backlog suite with `runtime/` on the path, and the core, integrations,
delivery, and harness suites with the plugin root and `scripts/` on the path. Tests that need a
settings file use `tests/settings_fixture.py`.

## Tests

- **Rules:** each rule has a deny case and an allow case, driven through
  `scripts/harness/hook.py` as a subprocess with Claude, Cursor, and Codex payload shapes. Evidence tests
  prove that a change after a check or a review makes the evidence stale.
- **Fail-closed behavior:** invalid settings block writes and allow reads; an unusable selected
  tracker refuses tracker writes; no active session refuses governed code changes.
- **Adapter boundary:** tests confirm host payloads normalize before policy evaluation and host
  response envelopes are emitted only by adapters.
- **Installer:** CI builds the release archive and installs it into sandboxed Claude Code and Codex
  profiles and a Cursor directory, then checks plugin registration and `harness doctor`.

## Full Outcome Gate

The gate in [development.md](development.md#full-outcome-gate), which CI runs on every pull request.

## Definition of Done

All suites green on Python 3.12 and 3.13; no skipped rule tests.

## Common Failure Modes

What the suites do **not** prove, and how it is covered instead:

| Gap | Covered by |
| --- | --- |
| The hooks firing inside a live Claude Code session | release gate: manual smoke test after install (see [../06-delivery/release-process.md](../06-delivery/release-process.md)) |
| Loading in Cursor | release gate; pending first observation |
| Codex hook trust and live invocation | release gate: review the installed hooks through `/hooks`, then observe one deny and one approved write |
| Calls against a live Azure DevOps organization | release gate: one read-only work-item fetch through `workflow-integrations` |
| Calls against a live Linear workspace | release gate: `harness doctor --tools` and a read-only issue fetch (the adapter's arguments follow Linear's documentation) |
| Skill quality (the model following a procedure well) | review of real runs; not unit-testable |
