---
title: Documentation Changelog
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Changelog

## 2026-09-26: Trackers, settings, and sessions (0.2.0)

- Every document now names `.harness/settings.json` as the only settings file; `policy.json`,
  `integrations.json`, and the backlog config are gone from the docs as from the code.
- Added the tracker contract (`tracker.json` plus `adapter.py`), onboarding and typed trust,
  sessions, and the `tracker-invalid` rule to the architecture, data model, API, components,
  workflows, security, threat model, runbook, troubleshooting, and user guide.
- Rewrote ADR-0009 (trackers are adapters, settings are one file) and amended ADR-0008's layout.
- Added glossary entries for adapter, checkout, gateway, onboarded tracker, session, settings,
  tracker, tracker contract, tracker manifest, tracker policy, tracker trust, and tracking mode.
- Added the rework checkpoint log under `06-delivery/checkpoints/`.

## 2026-09-22 — Documentation baseline

- Added structured product, architecture, design, engineering, operations, security, delivery, and
  guide documentation.
- Recorded seven architecture decisions: hooks-first enforcement, per-repository opt-in, human-only
  approval windows, protected items never linked, Claude Code and Cursor only, installs from release
  archives, and the backlog/spec split.
- Documented the seven harness rules, the evidence model, the approval protocol, and the installer.
- Marked loading in Cursor and a live Azure DevOps run as pending observation.

This changelog describes the documentation. For release history, see the root
[CHANGELOG.md](../../CHANGELOG.md).
