---
title: Deployment
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-25
---

# Deployment

## Runtime / Host

The harness is deployed to developer machines, into Claude Code, Cursor, or Codex. There is no hosted harness server.

## Installation

```bash
curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash -s -- --scope user
```

While the repository is private:

```bash
gh release download --repo Monolith-INC/monolithic-dev-harness --pattern install.sh --output - | bash -s -- --scope user
```

What the installer does, in order:

```text
preflight   Python >= 3.12, git, tar; warns if npx is missing
hosts       --host, or auto: `claude`/`codex` on PATH, ~/.cursor present
version     --version, or latest via gh / GitHub API (token if set)
download    monolithic-dev-harness-<v>.tar.gz + SHA256SUMS; verify checksum
scope       user (default in these examples), or local for exactly one explicit project;
            all is removal-only and is bounded to explicit projects and Claude/Codex metadata
stage       the original ~/.local/share/monolithic-dev-harness/marketplace location
            for both scopes; one current package, replaced in place
Claude      marketplace add|update, plugin install|update
Cursor      copy to ~/.cursor/plugins/local/monolithic-dev-harness
Codex       register its local marketplace and plugin; pin absolute MCP paths;
            install assignment-governed review-role TOML agents in ${CODEX_HOME:-~/.codex}/agents
CLI         ~/.local/bin/harness for both scopes (the original command location)
receipt     record provenance with mode 0600; preserve foreign intermediate settings and backups
references  project registration index under HARNESS_HOME; scoped removal retains shared code
            while other projects reference it
```

Options: `--scope user|local|all`, `--project <dir>` (exactly one for local; repeatable for all),
`--host auto|claude|cursor|codex|all`, `--version <x.y.z>`, `--source <dir|archive>`,
`--purge`, `--uninstall`, `--yes`. Scope is prompted only from `/dev/tty`; noninteractive use
must pass `--scope` even with `--yes`. Full contract:
[../02-design/api.md](../02-design/api.md#installsh).

## Configuration

After installing, restart Claude Code or Codex (review and trust Codex plugin hooks through `/hooks`) or reload Cursor, then opt each repository in with
`harness bootstrap`. See [environments.md](environments.md).

Native Claude and Codex registrations are removed only when their listing proves both the installed
plugin and an owned marketplace root. A same-named foreign marketplace is reported as ambiguous
and preserved. Kimi uses modern `~/.kimi-code` by default and scans legacy `~/.kimi`; local Kimi
configuration is selected with `kimi --config-file PROJECT/.kimi-code/config.toml`. Zed
project `context_servers` entries are managed only when attributable to the first-party source.
Credentials and provider configuration remain native prerequisites; the installer never copies them.
The Kimi config-file convention is documented by [Kimi CLI](https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/configuration/config-files.md),
and Zed project context-server ownership follows [Zed project settings](https://github.com/zed-industries/zed/blob/main/crates/project/src/project_settings.rs).
Codex skips untrusted hooks, and some specialized tools do not invoke hooks at all; do not treat
the hook policy as a complete security boundary.

Installation and `harness bootstrap` preserve Codex feature preferences, including an explicit
`default_mode_request_user_input = false`. Native async availability is discovered from actual
root tool events; this feature flag does not disable the separately observed async transport.
A prepared native candidate does not count as delivered or answered. Typed recovery preserves the
same pending decision when no permitted native control is available. See the
[qualification evidence](../06-delivery/acceptance/codex-adapter/evidence.md).

## Health Checks

```bash
harness doctor            # tools, hosts, settings, tracker, session
harness doctor --installations --json --scope user|local|all [--project <dir>] \
  [--repair-id <id> ...] [--apply-repairs]
harness doctor --tools    # plus: the tracker's server offers every tool its manifest names
harness doctor --tools    # checks the selected tracker's declared tools
```

## State Inspection

See [observability.md](observability.md).

## Runbook

See [runbook.md](runbook.md).

## Recovery

Re-run the installer: it replaces the installed copy and re-registers the plugin. Local host
configuration that is already tracked cannot be silently untracked by Git; choose user scope or
untrack it manually before retrying.

## Rollback

```bash
curl -fsSL …/install.sh | bash -s -- --version <previous version>
```

Repositories keep their `.harness/settings.json` and state during ordinary removal. Releases before 0.2.0 read `policy.json` instead
and do not know the settings file; rolling back across 0.2.0 means re-running that release's
bootstrap.

## Evidence to Preserve

When reporting an installation problem: the installer output, `harness doctor` output, and
`claude plugin list` output.
