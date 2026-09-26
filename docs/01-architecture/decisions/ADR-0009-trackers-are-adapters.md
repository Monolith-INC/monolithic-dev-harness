---
title: ADR-0009 Trackers are adapters
status: Proposed
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# ADR-0009: Trackers are adapters

## Context

The harness workflow must work with more than Azure DevOps without allowing a tracker-specific
tool to bypass approval or protection rules.

## Decision

Each tracker has a versioned `tracker.json` manifest. The registry validates the manifest and
selects the active tracker. Shipped trackers live under the plugin; onboarding stores a tracker in
the repository’s `.harness/trackers/` directory. An onboarded tracker is selectable only when its
approved folder digest remains pinned by a non-revoked human approval.

The manifest maps tracker artifacts to the harness roles `containers`, `delivery_unit`, and `step`.
It also declares states, identifiers and their mention forms, attachments, text format, write
tools, settings, and documented sources. A tracker folder holds data only (manifest, MCP settings,
references); adapter code stays in `scripts/integrations/`.

Failure is closed. A broken onboarded folder hides only itself. A selected tracker that cannot be
loaded blocks MCP calls. Protected-item mention checks always include the default `#<id>` and
work item URL forms, with the tracker's own forms on top. An onboarded folder is pinned only by an
approval whose text says "tracker" and names it; one approval does not pin every folder.

## Consequences

- Later Stories can move Azure, Linear, and local mechanics into tracker folders without changing
  the harness workflow vocabulary. Until then the gateway's tracker operations cover the shipped
  trackers only; an onboarded tracker is used through its own MCP tools.
- A changed onboarded manifest does not silently alter write or protected-item policy.
- Bootstrap will need to persist the selected source when a pinned onboarded tracker shadows a
  shipped tracker of the same name.

## Status

Proposed pending the Feature design gate.
