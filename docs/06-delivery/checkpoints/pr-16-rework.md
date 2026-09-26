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
| 3 | Single `settings.json`: schema, loader, example (`harness/settings.py`); consumers still read the old files | partly done |
| 4 | Tracker contract, manifests, registry, trust store (`integrations/`) | done |
| 5 | Azure, Linear, local adapters; SCM (`integrations/scm.py`); transport; gateway | done |
| 6 | Rules: one tracker policy value, fail closed, restored protections | pending |
| 7 | Sessions wired into enforcement | pending |
| 8 | Onboarding and tracker trust | pending |
| 9 | Delete copies; bootstrap, backlog config, skills, docs | pending |
| 10 | Tests in `run.sh`, CI, lint, versions, changelog; push | pending |

## Notes

- The Linear adapter's tool arguments (`save_issue` with `team`, `labels`, `parentId`, `state`;
  `list_comments`/`save_comment` with `issueId`) follow Linear's MCP documentation as far as it
  could be checked offline; confirm against a live server.
- New tests: `tests/core`, `tests/integrations`, `tests/harness/test_settings.py` (52 passing).
- The branch does not pass the full suite between checkpoints 3 and 6: the hook, rules, bootstrap,
  and backlog runtime still read `policy.json` / `integrations.json`.

## Next

Step 3 rest and step 6: move the hook, rules, workflow runtime, checks, knowledge, and backlog
config onto `settings.load`; build the tracker policy value in the rules.
