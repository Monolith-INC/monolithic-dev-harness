---
title: Vision
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Vision

## Purpose

Give a team on Azure DevOps an AI delivery process it can trust: the agent does the backlog,
planning, implementation, and review work, and the team's rules hold even when the model forgets
them, misreads them, or is steered by content it reads.

## Problem

Teams adopting coding agents have prompts, skills, and conventions, but no process. Approval
steps are sentences in a prompt. Work item hierarchies are whatever the agent produced. Commits
arrive without tests. Review is optional. Every tool that touches the board, the repository, or
the pull request is one confident mistake away from writing somewhere it should not.

## Users / Owner

- **Feature Owner / PO:** approves the backlog split and bodies (gate G1) and validates in staging
  (G3).
- **Tech Lead:** approves the technical spec (G2) and the pull request (G4).
- **Developer:** runs the harness in Claude Code or Cursor and answers approval batches.
- **Owner:** the monolithic-dev-harness maintainers.

## Goals

- One linear flow from an idea to a reviewed draft pull request, with each stage consuming the
  previous stage's output.
- People decide at four named gates; everything else is automated.
- Every rule that must always hold is enforced by a hook with tests, not by prose.
- One command installs it; re-running the command upgrades it.

## Non-Goals

- Replacing Azure Boards or Azure Repos, or adding columns and states to the board.
- Merging pull requests, voting, or publishing drafts: those stay human.
- Supporting hosts other than Claude Code and Cursor.
- Judging things no script can decide deterministically (for example whether personal data is
  masked in a UI); those stay in the review stage.

## Success Evidence

- A Story taken from idea to draft pull request with every gate recorded as an approval batch.
- Zero writes to Azure DevOps without an approval window, and zero writes to protected items.
- Test suites and CI green on every change; the installer verified in a sandboxed host profile.
