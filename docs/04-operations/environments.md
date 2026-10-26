---
title: Environments
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Environments

## Runtime / Host

| Host | Status | Plugin location |
| --- | --- | --- |
| Claude Code | supported; install verified in a sandboxed profile in CI | Claude's plugin cache, registered from `~/.local/share/monolithic-dev-harness/marketplace` |
| Cursor | supported; load pending first observation | `~/.cursor/plugins/local/monolithic-dev-harness` |

Operating systems: Linux and macOS. Windows is not supported (the installer and hooks assume a
POSIX shell).

## Installation

See [deployment.md](deployment.md).

## Configuration

| Setting | Where | Written by |
| --- | --- | --- |
| `.harness/settings.json` | repository (committed) | people; `harness bootstrap` copies a first version in once |
| `.harness/trackers/<name>/` | repository (committed) | `harness tracker stage`; trusted only by the user's click (or `approve HT-XXXXXX` in Cursor) |
| `Tickets/` | repository (project content) | the local tracker, when it is selected: the agile-backlog-toolkit's ticket files |
| `.harness/review/sources.json` | repository | the `review-setup` skill |
| `HARNESS_HOME`, `HARNESS_BIN_DIR`, `CURSOR_PLUGIN_DIR` | installer environment | optional overrides |

A governed repository commits `.harness/settings.json` and ignores `.harness/state/` (bootstrap adds
the ignore line to `.git/info/exclude`, this clone only). The local tracker's `Tickets/` is project
content, like any backlog the toolkit keeps.

## Health Checks

`harness doctor` in the repository.

## State Inspection

See [observability.md](observability.md).

## Runbook

See [runbook.md](runbook.md).

## Recovery

Delete `.harness/state/` to clear all approvals, evidence, sessions, tracker trust, and the
tracking mode; nothing else depends on it. Sessions then need starting again.

## Rollback

Remove `.harness/settings.json` to stop governing a repository (the rules stop applying at once).

## Evidence to Preserve

`.harness/state/approvals/` records every write made inside each window; keep it when auditing a
run.
