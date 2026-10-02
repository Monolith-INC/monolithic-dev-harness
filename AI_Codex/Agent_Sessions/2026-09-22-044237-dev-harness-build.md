---
title: Dev harness build
type: agent-session
timestamp: 2026-09-22T04:42:37-03:00
created: 2026-09-22
status: closed
branch: main
next: "[[2026-09-22-052910-org-neutral-config]]"
tags:
  - dev-harness
  - spike
---

# Dev harness build

Previous session: none (first session in this repository).
Canonical plan: `~/.claude/plans/noble-napping-fountain.md` (approved 2026-09-22).

## Goal

Build `monolithic-dev-harness` as a self-contained Claude Code + Cursor plugin: Azure DevOps skill,
linear backlog flow (agile-backlog-toolkit), Feature Owner delivery (codex-workflows) with
spec-driven execution (pstack / cursor-team-kit), review (thermos + review-story-preflight), and
deterministic hooks. Build only; the live demo on a copy of Idea 4007 happens later with the team.

## Constraints

- No Azure DevOps writes in this session (read-only health checks only).
- Do not touch the aplicatudo-monorepo main checkout (uncommitted work on `userstory/7824-…`) or
  the dirty agile-backlog-toolkit working tree; sources are copied from committed HEAD.
- Baseline: Idea 4007 is at `System.Rev` 20.

## Progress

- [x] Repo scaffold (`git init`, plugin layout).
- [x] Azure DevOps skill ported: runtime namespace discovery, portable dependency-free
      `health-check.mjs` (verified healthy), `references/tool-map.md` (current `tool[action]` names).
- [x] Backlog toolkit copied from `e7ae82c`.
- [x] Legacy Azure tool names replaced across backlog skills (13 files → `tool[action]`).
- [x] Epic→Feature gap closed in `decompose-backlog` (tree mode, same two gates); Story Points
      mandatory in the Azure field with read-back.
- [x] Delivery (codex-workflows @ `75c22f0`), spec-driven execution (`implement-story`, `architect`,
      `tdd`, `check`, `deslop`, `prove-it-works`, `branch-and-pr`), review (`review`,
      `review-story-preflight`, thermos), `harness` conductor, `bootstrap`.
- [x] Hooks: rules H0–H6 (`scripts/harness/`) + codex-workflows policy, wired for Claude and Cursor;
      repos opt in via `.harness/policy.json`.
- [x] Tests: backlog 362 passed / 1 skipped; delivery + harness 173 passed (21 hook-rule tests).
- [x] `claude plugin validate` passes; clean-profile install loads 46 skills. 4007 still Rev 20.

## Open

- Cursor load not verified (needs the user in the Cursor GUI); `${CURSOR_PLUGIN_ROOT}` in
  `cursor.mcp.json` is unverified.
- Harness license (`UNLICENSED` placeholder) and git remote not decided; nothing committed.
- Test/rehearsal plan for the live demo on the 4007 copy: to decide with the user.
