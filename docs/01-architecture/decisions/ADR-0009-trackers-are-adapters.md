---
title: ADR-0009 Trackers are adapters
status: Proposed
date: 2026-09-25
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
It also declares states, identifiers, mention behaviour, attachments, text format, write tools,
settings, and documented sources. Invalid active manifests fail closed.

## Consequences

- Later Stories can move Azure, Linear, and local mechanics into tracker folders without changing
  the harness workflow vocabulary.
- A changed onboarded manifest does not silently alter write or protected-item policy.
- Bootstrap will need to persist the selected source when a pinned onboarded tracker shadows a
  shipped tracker of the same name.

## Status

Proposed pending the Feature design gate.
