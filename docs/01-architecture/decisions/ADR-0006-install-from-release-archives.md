---
title: ADR-0006 Install from release archives
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
---

# ADR-0006: Install from checksum-verified release archives, in one command

## Status

Accepted

## Context

Asking users to clone the repository, add a marketplace by path, and wire each host by hand
produces broken installs. Installation must be one command, repeatable, and reversible.

## Decision

Each release publishes `monolithic-dev-harness-<version>.tar.gz`, `install.sh`, and
`SHA256SUMS`. `install.sh` resolves the version, downloads the archive (through `gh`, a token, or
public HTTPS), verifies its checksum, registers it with Claude Code (a local marketplace) and/or
copies it to Cursor's local plugins directory, records the Azure DevOps organization, and links
the `harness` command. Re-running upgrades; `--uninstall` reverses everything.

## Options Considered

- **`git clone` + manual wiring:** requires repository access and manual steps.
- **Claude marketplace from GitHub:** Claude-only and still clones behind the scenes.
- **Release archive + installer (chosen).**

## Consequences

### Positive

- Users never clone; the installed bytes are exactly the released bytes.
- The same installer serves Claude Code, Cursor, and Codex and pins versions on request.

### Trade-offs

- While the repository is private, downloading needs `gh` or a token.

## Host-specific Impact

Claude Code gets the archive as a local marketplace and the organization in its settings `env`;
Cursor gets a plugin copy with the organization pinned in `cursor.mcp.json`.

## Validation

CI builds the archive and installs it into a sandboxed Claude Code profile; the release workflow
publishes only after tests pass.

## References

- [../../04-operations/deployment.md](../../04-operations/deployment.md)
