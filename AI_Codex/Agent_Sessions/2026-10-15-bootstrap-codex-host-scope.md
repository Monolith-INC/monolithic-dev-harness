---
title: Scope the Codex picker setting to Codex during bootstrap
type: agent-session
timestamp: 2026-10-15T01:42:34-03:00
created: 2026-10-15
status: active
branch: codex/planning-and-interaction-reliability
next: null
tags:
  - dev-harness
  - bootstrap
---

# Scope the Codex picker setting to Codex during bootstrap

Previous session: [[2026-09-22-062208-repo-grooming]]

## Goal

Bootstrap writes `.codex/config.toml` only when setup runs on Codex (`--host codex`); other hosts
get no `.codex` folder. Update tests and commit.

## Progress

- [x] Tests pass `--host codex` where they expect the Codex picker setting.
- [x] Test that a non-Codex host gets no `.codex` folder.
- [x] Bootstrap tests green on Python 3.12+; commit.
