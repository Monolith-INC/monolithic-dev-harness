---
title: PR 16 rework checkpoints
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# PR 16 rework checkpoints

Progress log for reworking PR 16 (`codex/scoped-sessions`) after the thermos review. Update the
table and the "Next" line at every milestone, so work can resume from here.

## Decisions (from the user)

- Copies are forbidden: one source of truth for every file, value, and rule.
- One settings file per repository, `.harness/settings.json`. People edit it; the agent cannot; the
  code reads it once and never writes it. It replaces `policy.json`, `integrations.json`, and
  `backlog/config.json`.
- Clean break: the harness is not in production, so no migration of old layouts or old names.
- Every tracker adapter meets one contract: the `tracker.json` schema (data) plus the adapter
  interface (operations). Azure, Linear, and local are rewritten from scratch.
- Functional style in new code: steps return `Ok`/`Err` values instead of raising, `match` for
  branching, no mutation, exceptions caught only at the edges. Standard library only.
- `sessions.py` is implemented properly (wired into enforcement, typed, tested), not removed.

## Design

```text
trackers/<name>/        the only definition of a tracker
  tracker.json          data contract: kinds, states, ids, mentions, writes, connection, settings
  adapter.py            translation only; exports adapter(context) -> TrackerOps
scripts/core/           result.py (Ok/Err), schema.py (stdlib JSON Schema subset)
scripts/integrations/   contracts (TrackerOps, ScmOps, domain types), registry, transport, gateway
.harness/settings.json  the only settings file (human-owned)
.harness/state/         approvals, sessions, tracker trust, tracking mode (hook-written only)
```

- Tracker lookup returns one of: not configured, active, invalid. Invalid blocks remote writes.
- A broken onboarded folder is reported on its own; it does not break the others.
- Onboarded trackers are trusted only by the user typing `harness trust-tracker <name> <digest>`.
- Sessions bind a work item to one checkout; governed code changes need an active session.

## Steps

| # | Step | Status |
|---|------|--------|
| 1 | Map current code and baseline tests (main: 233 delivery+harness, 366 backlog pass) | done |
| 2 | Core: `Ok`/`Err` values and stdlib schema validator (`scripts/core/`) | done |
| 3 | Single `settings.json`: every reader moved (hook, rules, runtime, checks, knowledge, backlog), old loaders deleted | done |
| 4 | Tracker contract, manifests, registry, trust store (`integrations/`) | done |
| 5 | Azure, Linear, local adapters; SCM (`integrations/scm.py`); transport; gateway | done |
| 6 | Rules: `TrackerPolicy` built once, `tracker-invalid` rule, restored protections, typed settings | done |
| 7 | Sessions wired into the workflow runtime; `harness session` command | done |
| 8 | Onboarding (`harness tracker stage/show/list`) and typed trust in the prompt hook | done |
| 9 | Bootstrap and backlog config done; skills, references, and docs still name the old files | in progress |
| 10 | Tests in `run.sh`, CI, lint, versions, changelog; push | pending |

## Notes

- The Linear adapter's tool arguments (`save_issue` with `team`, `labels`, `parentId`, `state`;
  `list_comments`/`save_comment` with `issueId`) follow Linear's MCP documentation as far as it
  could be checked offline; confirm against a live server.
- Full runner (`tests/run.sh`) passes: 347 backlog, 268 core/integrations/delivery/harness.
- Still to update in step 9: skills (`bootstrap`, `onboard-tracker`, `start-ticket`,
  `enrich-work-item`, `generate-work-item`, `generate-breakdown-work-items`, `skip-tracker`,
  `resume-tracker`, `azure-devops`, `generate-plain-language-documentation`), `references/`
  (`project-config.md`, `azure-mechanics.md`), docs, README, ADR-0009, CHANGELOG, versions, CI.

## Next

Step 9: rewrite the skills and docs that name `policy.json`, `integrations.json`, the backlog
config file, or `config --set`; one shared tracker-contract reference for the three work-item
skills. Then step 10.
