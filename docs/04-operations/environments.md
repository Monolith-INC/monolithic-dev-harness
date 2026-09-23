---
title: Environments
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
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
| `AZURE_DEVOPS_ORG` | Claude `settings.json` → `env`; Cursor `cursor.mcp.json` (pinned) | installer (`--org`) |
| `.harness/policy.json` | repository (committed) | `harness bootstrap`, then people |
| `.harness/integrations.json` | repository | bootstrap: Azure Boards tracker, Azure Repos SCM, branch template |
| `.harness/backlog/config.json` | repository | bootstrap: org, project, team, artifacts path, `provider_mode: azure` |
| `.harness/review/sources.json` | repository | the `review-setup` skill |
| `HARNESS_HOME`, `HARNESS_BIN_DIR`, `CURSOR_PLUGIN_DIR` | installer environment | optional overrides |

A governed repository commits `.harness/policy.json` and ignores `.harness/state/` (bootstrap adds
the ignore line).

## Health Checks

`harness doctor` in the repository.

## State Inspection

See [observability.md](observability.md).

## Runbook

See [runbook.md](runbook.md).

## Recovery

Delete `.harness/state/` to clear all approvals and evidence; nothing else depends on it.

## Rollback

Remove `.harness/policy.json` to stop governing a repository (the rules stop applying at once).

## Evidence to Preserve

`.harness/state/approvals/` records every write made inside each window; keep it when auditing a
run.
