---
title: ADR-0002 Per-repository opt-in
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# ADR-0002: Govern only repositories that opt in

## Status

Accepted

## Context

Plugins install at the user level, so their hooks run in every repository the developer opens. An
earlier workflow plugin blocked writes in unrelated repositories because they lacked its
configuration.

## Decision

A repository is governed only when it contains `.harness/settings.json`, written by
`harness bootstrap`. Everywhere else the hook runtime allows every call and does not consult the
workflow policy.

## Options Considered

- **Govern everything, fail closed without configuration:** safe but blocks unrelated work.
- **Per-repository opt-in (chosen):** the settings file is both the switch and the configuration.

## Consequences

### Positive

- Installing the plugin never breaks work in other repositories.
- The settings that enable governance are reviewed and committed like code.

### Trade-offs

- A repository is unprotected until someone runs bootstrap.

## Host-specific Impact

None.

## Validation

`TestOptIn.test_repo_without_settings_is_not_governed` in `tests/harness/test_hook_rules.py`.

## References

- [ADR-0001](ADR-0001-deterministic-enforcement-in-hooks.md)
