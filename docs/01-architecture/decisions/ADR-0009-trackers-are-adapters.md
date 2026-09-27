---
title: ADR-0009 Trackers are adapters
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# ADR-0009: Trackers are adapters, settings are one file

## Status

Accepted and implemented in 0.2.0.

## Context

The harness workflow must run on more than Azure DevOps without letting a tracker-specific tool
bypass approval or protection rules. Before this decision, Azure behaviour was spread through the
gateway, bootstrap, and the rules; the tracker's connection, tool names, and state names were
copied into each repository's `integrations.json`; and a repository's settings were split over
`policy.json`, `integrations.json`, and the backlog config, read by three loaders.

## Decision

1. **One contract.** A tracker is one folder, `trackers/<name>/`, holding `tracker.json` and
   `adapter.py`. `tracker.json` is checked against `config/tracker.schema.json` and the registry's
   own rules (hierarchy, id expressions, settings). `adapter.py` exports
   `adapter(context) -> TrackerOps`, a record of functions each returning `Ok` or `Err`
   (`scripts/integrations/contracts.py`). Every function is required, sprint planning included
   (`read_iteration`, `iteration_items`, `hour_fields`), and `tracker.json` lists the replies that
   planning reads. Azure DevOps, Linear, and the local tracker ship this way; nothing about a
   tracker lives outside its folder, and the backlog runtime reads sprints only through it.
2. **One source per value.** The manifest owns kinds, states, hierarchy, id formats, mention
   forms, write tools, tool names, and how to connect. The repository's `.harness/settings.json` owns
   only the choice and the values the manifest asks for. Shared templates stay in
   `common/templates/`, shared references in `references/`.
3. **One settings file.** `.harness/settings.json` replaces `policy.json`, `integrations.json`, and
   `backlog/config.json`. It is human-owned: people write it, the harness reads it once per process
   into a value nothing can change, and defaults for omitted sections live in one loader.
4. **Fail closed.** The registry checks each folder on its own and reports a broken one without
   hiding the others. The selected tracker resolves to not configured, active, or invalid; anything
   but active refuses tracker and SCM writes (`tracker-invalid`). When the rules cannot run, every
   MCP call counts as a write.
5. **Rules read every usable tracker.** Which calls write, how ids look, and which text links come
   from every shipped or trusted tracker, not only the selected one, because the Azure DevOps server
   is registered with the host whatever a repository selects.
6. **Trust is typed by a person.** An onboarded tracker (`.harness/trackers/<name>/`) counts only
   while its folder matches the digest the user typed in `harness trust-tracker <name> <digest>`.
   Editing any file drops trust. A generic approval never trusts a tracker.
7. **Standard library only.** The schema checker is the harness's own (`scripts/core/schema.py`),
   because the hooks run before every tool call on machines with no extra packages.
8. **Sessions scope enforcement.** A session binds one work item to one checkout; governed code
   changes need an active one, and the workflow checks that item.

## Options Considered

- **Keep Azure in the gateway and add Linear beside it:** two code paths to keep equal, and the
  rules would still assume Azure id formats.
- **Manifest only, adapters as a fixed list in code:** every new tracker would need a harness
  release, and onboarded trackers could not bring their own translation.
- **Validate manifests with `jsonschema`:** a third-party package in the hook path, which breaks
  every write where it is missing.
- **Folder contract, one settings file, typed trust (chosen).**

## Consequences

### Positive

- A new tracker is a folder; the workflow vocabulary does not change.
- A changed onboarded tracker cannot silently alter write or protection policy.
- There is one place to read or change any setting.

### Trade-offs

- Clean break: repositories set up before 0.2.0 re-run bootstrap with a settings file.
- The rules load and check every tracker folder on each call (milliseconds; counted in the hook's
  time budget).
- The Linear adapter's tool arguments follow Linear's documentation and still need a live check.

## Host-specific Impact

None: both hosts use the same hook, gateway, and folders.

## Validation

`tests/integrations/` (registry, adapters, gateway, trust, onboarding), `tests/harness/test_hook_rules.py`
(`TestTrackers`, `TestProtected`), `tests/harness/test_settings.py`, `tests/harness/test_sessions.py`.

## References

- [ADR-0004](ADR-0004-protected-items-are-never-linked.md)
- [ADR-0008](ADR-0008-the-harness-owns-its-files.md)
- [../../02-design/api.md](../../02-design/api.md)
