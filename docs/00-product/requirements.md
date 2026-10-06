---
title: Requirements
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
---

# Requirements

## Purpose

State what the harness must do, in order of priority, so changes can be judged against it.

## Problem

See [vision.md](vision.md). The requirements below turn the optional definition stage, four delivery
stages, and the team's rules into testable obligations.

## Users / Owner

Feature Owner / PO, Tech Lead, developers; owned by the monolithic-dev-harness maintainers.

## Goals

Cover technical discovery of assigned feature requests, backlog management, technical planning,
implementation, and verification. Keep product ideation available as an optional route, and explain
how the process uses the team's tracker and where people make decisions.

## Non-Goals

See [vision.md](vision.md#non-goals).

## Requirements

### Must

- **Technical discovery:** start from an assigned ticket or draft feature request; inspect the
  existing repository, research implementation options, and produce a reviewed feature plan before
  backlog drafting. Keep optional product ideation available when requested.
- **Backlog:** decompose an Epic into Features and Stories in one run with two approval gates;
  write Story Points into the process's Azure points field and read them back; break Stories into
  atomic Tasks plus Staging, Review, and a done Breakdown Task; audit coverage against the source
  text and product capability IDs when present.
- **Planning:** produce a technical spec per Story from the backlog output, reviewed by a critic,
  inheriting product, UX, and architecture decisions, and approved by a person before implementation.
- **Implementation:** one verified commit per Task, test first where practical.
- **Verification:** check requirements coverage against the Story's acceptance criteria, then run a
  deep correctness and maintainability audit, then record a verdict tied to the exact commit.
- **Enforcement:** block tracker/SCM writes and `git push` without a human-opened approval window;
  never write, link, or parent protected work items; block commits of source changes without
  tests; block hand edits to generated files; require evidence for guarded paths; create pull
  requests only as drafts with a `ready` verdict and passing checks for HEAD.
- **Safety:** fail closed for writes when the rules cannot run or the settings or selected tracker
  cannot be used; govern only repositories that opt in.
- **Trackers:** every tracker meets one contract (a checked `tracker.json` and an adapter); Azure
  DevOps, Linear, and a repository-local tracker ship; others can be onboarded, and count only once
  a person trusts them as they read.
- **Scope:** governed code changes happen inside a session that binds one work item to one
  checkout.
- **Hosts:** Claude Code, Cursor, and Codex.
- **Install:** one command, no cloning, checksum-verified, idempotent; uninstall supported.

### Should

- Report every block with the rule's name and the fix.
- Keep project-specific values (paths, commands, ids) in the repository's one settings file, and
  tracker-specific ones in tracker folders, not in the plugin's code.
- Provide a `harness doctor` health check.

### Could

- Trigger stages from Azure DevOps events (service hooks, pipelines).
- Record per-stage token usage automatically.

### Won't

- Merge pull requests or vote on them.
- Store credentials; the providers' MCP servers use interactive OAuth.

## Success Evidence

Each Must has tests: `tests/harness/test_hook_rules.py` for enforcement, `tests/integrations/` for
the tracker contract and adapters, `tests/harness/test_sessions.py` for sessions,
`tests/backlog/` for validation, estimation, and capacity, `tests/delivery/` for the workflow
policy runtime, and the CI installer job for installation.

## Constraints

- Python 3.12+ on the developer's machine (standard library only in hooks); Node.js for the Azure
  DevOps and Linear MCP servers.
- Hooks must answer within the host's hook timeout (15 s for pre-tool calls).

## Open Questions

- Whether the model-per-stage split measurably lowers cost without lowering quality; to be
  measured on real Stories.
