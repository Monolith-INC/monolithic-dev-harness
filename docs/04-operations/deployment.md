---
title: Deployment
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Deployment

## Runtime / Host

The harness is deployed to developer machines, into Claude Code and/or Cursor. There is no server.

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
hosts       --host, or auto: `claude` on PATH, ~/.cursor present
version     --version, or latest via gh / GitHub API (token if set)
download    monolithic-dev-harness-<v>.tar.gz + SHA256SUMS; verify checksum
stage       ~/.local/share/monolithic-dev-harness/marketplace   (atomic replace)
Claude      marketplace add|update, plugin install|update, env.AZURE_DEVOPS_ORG in settings.json
Cursor      copy to ~/.cursor/plugins/local/monolithic-dev-harness, pin the org in cursor.mcp.json
CLI         ~/.local/bin/harness -> the installed bin/harness
```

Options: `--host auto|claude|cursor|all`, `--org <name>`, `--version <x.y.z>`,
`--source <dir|archive>`, `--uninstall`, `--yes`. Full contract:
[../02-design/api.md](../02-design/api.md#installsh).

## Configuration

After installing, restart Claude Code or reload Cursor, then opt each repository in with
`harness bootstrap`. See [environments.md](environments.md).

## Health Checks

```bash
harness doctor                                   # tools, hosts, configuration, repository
harness doctor --azure --project <project>       # plus a live Azure DevOps call (opens OAuth)
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

Repositories keep their `.harness/policy.json`; older releases ignore fields they do not know.

## Evidence to Preserve

When reporting an installation problem: the installer output, `harness doctor` output, and
`claude plugin list` output.
