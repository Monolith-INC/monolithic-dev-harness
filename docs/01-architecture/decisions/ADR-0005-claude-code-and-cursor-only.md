---
title: ADR-0005 Claude Code and Cursor only
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# ADR-0005: Support Claude Code and Cursor only

## Status

Accepted

## Context

The source toolkits supported up to five hosts (Claude Code, Cursor, Codex, Gemini, Antigravity),
each with its own hook payloads, installers, and metadata. The team uses Claude Code and Cursor.

## Decision

Ship adapters, hooks, manifests, and installer support for Claude Code and Cursor only. Code,
fixtures, and metadata for other hosts were removed.

## Options Considered

- **Keep all five hosts:** more surface to test and maintain with no users.
- **Claude Code only:** leaves Cursor users out.
- **Claude Code and Cursor (chosen).**

## Consequences

### Positive

- One hook entry point with two payload formats; smaller runtime and test surface.

### Trade-offs

- Adding a host later means re-adding an adapter and its tests.

## Host-specific Impact

See [../architecture.md](../architecture.md#host-differences).

## Validation

Hook tests cover both hosts' payloads; CI installs into a sandboxed Claude Code profile. Cursor
loading is pending observation.

## References

- [../../../THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md)
