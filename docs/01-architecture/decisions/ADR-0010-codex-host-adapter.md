---
title: ADR-0010 Codex host adapter
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# ADR-0010: Support Codex as a host

## Decision

Ship a Codex compatibility manifest, a Codex marketplace, host-specific hooks and MCP
configuration, and a payload adapter for the existing harness policy runtime. The installer
registers the marketplace through the Codex CLI and creates a separate plugin copy with absolute
MCP paths. It installs two read-only Codex custom-agent TOMLs in the Codex agents directory.
Codex must trust the installed hooks before they enforce policy.

The Codex hooks cover observed shell, patch, native question, collaboration and MCP names,
including observed concatenated aliases. Lifecycle hooks bind native children and revoke their
completed turns. The host adapter parses `apply_patch` file headers and passes every target as a
generic file path; host-specific parsing and JSON stay outside the shared policy rules.

Question transport depends on observed root capabilities and permitted decision class. Default
synchronous `request_user_input` is optional-only and cannot request permission or escalation.
The separately qualified async domain-review route binds the actual question to the pending
decision, then captures its later answer; immediate delivery acknowledgement never answers it.
`UserPromptSubmit` remains a conversation-bound typed recovery path. Neither typed recovery nor
protocol delivery qualifies visible structured controls in Desktop.

## Consequences

The hook and policy test suites cover Codex payloads and deny output. Live plugin loading remains
an installation verification step. Hook trust is a host requirement: an untrusted plugin hook is
skipped by Codex.
Some specialized tools do not invoke hooks; Codex hooks are not a complete security boundary.

This decision supersedes [ADR-0005](ADR-0005-claude-code-and-cursor-only.md).

## Current qualification work (2026-10-23)

The Codex adapter now distinguishes native child `agent_id` from the shared parent `session_id`,
using observed lifecycle events to freeze child work-session scope. Child observations do not
confer approval authority. The Python subprocess subagent contract remains unsupported; this
does not describe Codex's native model-facing delegation capability.

Question availability, collaboration mode, permitted decision class and actual delivery are
separate facts. `permission_mode` does not establish collaboration mode. In the confirmed
async wire contract, post-tool `accepted:true` acknowledges delivery; the later operator input
is a separate event. No timeout or delivery acknowledgement authorizes an effect.

See the [current evidence and official source anchors](../../06-delivery/acceptance/codex-adapter/evidence.md)
and [development trial](../../06-delivery/acceptance/codex-adapter/trial.md) for precise supported
boundaries and remaining release requirements. Native protocol observations do not yet qualify
a fully functional installed Desktop release.
