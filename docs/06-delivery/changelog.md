---
title: Documentation Changelog
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-06
---

# Changelog

## 2026-10-06: BMad depth restored, one way to ask

- Workflows: discovery depth model (subagent investigation, batched questions, scope re-check,
  memlog, Deepen), correct-course routing, end-to-end tests in Build, and the combined Verify audit.
- Vendor manifest: four new bundled BMad skills and the harness adaptations of each.
- Asking the human: menus and question batches (`workflows.md`), the rewritten decision contract,
  the standard-questions catalog (ADR-0011), and the ADR-0003 amendment for approvals tied to
  their context.
- Flow continuity: the stop guard in `workflows.md` and the architecture host table; the
  current work session (no session id needed) in the storyboard, harness skill, and decision
  contract.
- Spec: [harness-main-flow.md](../02-design/specs/harness-main-flow.md) maps stages, gates, and the interaction contract;
  its diagram lives in `docs/assets/diagrams/`.

## 2026-09-30: Codex host adapter (0.4.0)

- Documented the Codex marketplace, compatibility manifest, hook trust, MCP configuration, and
  read-only custom reviewers.
- Made the host-adapter boundary explicit: host payloads and response envelopes are translated
  outside the harness rules and workflow policy.
- Updated testing and release gates to cover Codex installation while keeping live hook trust and
  invocation as manual observations.

## 2026-09-30: Optional Stage 0 product planning

- Added a BMAD-inspired planning path that can turn an initial idea into a product brief, product
  requirements, experience decisions, an architecture spine, and a canonical product specification.
- The harness now offers **Plan the idea** or **Draft work items** through the same structured UI
  used for its other choices; selecting planning routes into Stage 0 without creating an approval
  window.
- Backlog, Story-specification, and Task-architecture skills now preserve traceability to Stage 0
  capability, requirement, experience, and architecture decisions.

## 2026-09-29: Adoption, Feature pinning, and click approvals (0.3.0)

- Documented `harness adoption` (assess, plan, status, materialize), the **Approve adoption** and
  **Approve change** buttons, and the human-owned `.harness/state/adoptions/` records in the data
  model, API, glossary, security controls, runbook, and user guide.
- Added the `feature-branch` rule to every rule list, and `session start --base-ref` to the API.
- `.harness/tracker/` is now local to the clone and shared by its worktrees (data model,
  environments, architecture).

## 2026-09-28: Release review (0.2.0)

- Trust and selection of onboarded trackers by click replace the typed trust line in the glossary,
  ADR-0009, API, security model, and user guide. The settings file's one harness write (the
  tracker the user chooses) is stated in full once, in the data model, and linked elsewhere.
- Sprint planning through the tracker contract (`read_iteration`, `iteration_items`,
  `hour_fields`, `planning.replies`) in ADR-0009 and the API; the user guide explains the capacity
  check during breakdown.
- Added the tech-debt register (`06-delivery/tech-debt.md`, TD-1 to TD-3).
- Removed hard-coded counts (skills, version sources) that nothing checks.

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
