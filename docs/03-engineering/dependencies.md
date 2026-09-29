---
title: Dependencies
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-28
---

# Dependencies

## Purpose

Everything the harness needs at runtime and in development, and why.

## Prerequisites

None beyond the tables below.

## Authoritative Source Files

`install.sh` (preflight), `pyproject.toml`, `.github/workflows/`, `.mcp.json`, `cursor.mcp.json`.

## Generated Files

None.

## Development Workflow

### Runtime (user machines)

| Dependency | Needed by | Notes |
| --- | --- | --- |
| Python 3.10+ (standard library only) | hooks, orchestrators, gateway, CLI | checked by the installer and `harness doctor` |
| git | hooks | trees, staged paths, branch diffs |
| Node.js / `npx` | `@azure-devops/mcp` | downloaded by `npx` on first start |
| `@azure-devops/mcp` | Azure DevOps access | interactive OAuth; the gateway passes the settings' organization, the host-registered server reads `AZURE_DEVOPS_ORG` |
| `mcp-remote` | Linear access, when selected | started by `npx`; OAuth in the browser |
| Claude Code and/or Cursor | host | |
| `curl` or `gh` | installer | `gh` or a token while the repository is private |

### Development and CI

| Dependency | Version | Purpose |
| --- | --- | --- |
| pytest | latest | test runner |
| ruff | 0.16.4 (pinned) | lint and format |
| shellcheck | 0.11 (via `shellcheck-py` locally, preinstalled in CI) | shell lint |
| Claude Code CLI | latest | `claude plugin validate`, sandboxed install test |
| GitHub Actions | `actions/checkout`, `actions/setup-python`, `actions/setup-node` | CI and release; Dependabot keeps them current |

### Vendored sources

The plugin is assembled from internal and MIT-licensed sources; see
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

## Tests

CI runs on Python 3.10 and 3.12.

## Full Outcome Gate

See [development.md](development.md#full-outcome-gate).

## Definition of Done

A new runtime dependency is justified here and checked by the installer's preflight.

## Common Failure Modes

A GUI-launched host may not see the shell's `PATH` (for example `nvm`'s Node). `harness doctor` and
the runbook cover it.
