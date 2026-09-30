---
title: Deployment
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Deployment

## Runtime / Host

The harness is deployed to developer machines, into Claude Code, Cursor, or Codex. There is no hosted harness server.

## Installation

```bash
curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash
```

While the repository is private:

```bash
gh release download --repo Monolith-INC/monolithic-dev-harness --pattern install.sh --output - | bash
```

What the installer does, in order:

```text
preflight   python3 >= 3.10, git, tar; warns if npx is missing
hosts       --host, or auto: `claude`/`codex` on PATH, ~/.cursor present
version     --version, or latest via gh / GitHub API (token if set)
download    monolithic-dev-harness-<v>.tar.gz + SHA256SUMS; verify checksum
stage       ~/.local/share/monolithic-dev-harness/marketplace   (atomic replace)
Claude      marketplace add|update, plugin install|update, env.AZURE_DEVOPS_ORG in settings.json
Cursor      copy to ~/.cursor/plugins/local/monolithic-dev-harness, pin the org in cursor.mcp.json
Codex       register its local marketplace and plugin; pin absolute MCP paths and Azure organization;
            install two managed read-only custom agents in ${CODEX_HOME:-~/.codex}/agents
CLI         ~/.local/bin/harness -> the installed bin/harness
```

Options: `--host auto|claude|cursor|codex|all`, `--org <name>`, `--version <x.y.z>`,
`--source <dir|archive>`, `--uninstall`, `--yes`. Full contract:
[../02-design/api.md](../02-design/api.md#installsh).

## Configuration

After installing, restart Claude Code or Codex (review and trust Codex plugin hooks through `/hooks`) or reload Cursor, then opt each repository in with
`harness bootstrap`. See [environments.md](environments.md).
Codex skips untrusted hooks, and some specialized tools do not invoke hooks at all; do not treat
the hook policy as a complete security boundary.

## Health Checks

```bash
harness doctor            # tools, hosts, settings, tracker, session
harness doctor --tools    # plus: the tracker's server offers every tool its manifest names
harness doctor --azure    # plus: a live Azure DevOps call with the settings' values (opens OAuth)
```

## State Inspection

See [observability.md](observability.md).

## Runbook

See [runbook.md](runbook.md).

## Recovery

Re-run the installer: it replaces the installed copy and re-registers the plugin.

## Rollback

```bash
curl -fsSL …/install.sh | bash -s -- --version <previous version>
```

Repositories keep their `.harness/settings.json`. Releases before 0.2.0 read `policy.json` instead
and do not know the settings file; rolling back across 0.2.0 means re-running that release's
bootstrap.

## Evidence to Preserve

When reporting an installation problem: the installer output, `harness doctor` output, and
`claude plugin list` output.
