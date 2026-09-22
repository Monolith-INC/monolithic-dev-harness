---
name: harness
description: The end-to-end AI delivery flow for an Azure DevOps team — backlog (Epic → Features → Stories with points → Tasks), technical spec, spec-driven implementation, requirements-first review, and a draft pull request — with human gates G1–G4 and hook-enforced rules. Use when the user wants to take an idea or work item through the whole process, asks "what's next" in a harness run, or asks how the process works.
---

# Harness

One linear flow. Each stage consumes the previous stage's output; none re-invents it. Humans decide
at four gates. Hooks enforce the rules that must never depend on the model remembering them.

```
 idea / work item
      │
 1 BACKLOG ───── generate-work-item → enrich-work-item → decompose-backlog → generate-breakdown-work-items
      │           (top ancestor draft)  (team format)     (Epic→Features→Stories,  (Tasks + Staging/
      │                                                     points)                  Review/Breakdown)
      ├── G1  Feature Owner / PO approve the split and the bodies before any Azure write
 2 PLAN ──────── start-ticket → write-spec (Actor-Critic)
      ├── G2  Tech Lead approves the spec
 3 BUILD ─────── implement-story: per Task architect → tdd → implement → check → deslop → commit
 4 VERIFY ────── review: review-story-preflight → thermos → fixes → verdict → branch-and-pr (draft)
      ├── G3  Feature Owner validates in staging
      └── G4  a human publishes and approves the pull request
```

Stacked Feature work (several Stories under one Feature) runs stage 3–4 per Story inside
`feature-implementation`, then `merge-story-stack-into-feature` and `finish-feature-development`.

## Before the first run in a repository

The repository must be opted in: `.harness/policy.json` exists (run `bootstrap`), Azure DevOps
answers a health check (`azure-devops`), and `review-setup` has run. If any is missing, do that
first and say so.

## Stage 1: Backlog

1. **Top ancestor.** `generate-work-item` drafts the highest item in the tree (usually an Epic) from
   the user's idea or an existing item. The **Descrição Original** section keeps the source text
   verbatim. The top ancestor can be a Feature or a User Story: neither needs a parent, so do not
   ask for or invent one. When the source is an item that must stay intact (for example, the
   original of a copied item), create a new item and cite the original by URL in its description.
   Never link to it: links are two-way and change the original. Protected ids are blocked by rule
   `protected-items`.
2. **Enrich** it (`enrich-work-item`) into the team format.
3. **Decompose** (`decompose-backlog`, tree mode for an Epic): Features, then Stories with points,
   one outline at GATE 1 and one body batch at GATE 2. Points go into the Azure points field.
4. **Break down** each Story that will be built next (`generate-breakdown-work-items`): atomic Tasks
   aligned to the acceptance criteria, plus Staging, Review, and a done Breakdown Task.
5. `validate-artifact` on anything the user edited by hand.

## Stage 2: Plan

`start-ticket` on the Story (moves it to in progress), then `write-spec`. The spec takes the
Story, its acceptance criteria, and its Tasks as input and decides the *how*: architecture, affected
modules, test strategy, UI design notes. Present it for **G2** and stop until the user approves.

## Stage 3: Build

`implement-story`. One Task, one verified commit, in breakdown order.

## Stage 4: Verify

`review`. The requirements check first, then thermos, fixes, a verdict for HEAD, and the draft PR.

## The approval protocol (every tracker or SCM write)

Hook `approval-required` blocks every write to Azure DevOps (work items, links, comments, pull requests, threads,
branches, `git push`) unless the user has opened an approval window. To open one:

1. Show the exact batch: each item or field or link, or the push and PR you are about to make.
2. Give it a batch id: `HB-` plus 4–8 uppercase letters or digits (for example `HB-7Q2K`).
3. Ask the user to reply `approve HB-7Q2K` (`aprovo HB-7Q2K` also works). Their prompt opens the
   window for `approvals.window_minutes` (default 20). `harness revoke` closes it early.

You cannot open the window yourself: approval records are written only by the prompt hook, and
hook `human-owned` blocks any agent write to them. Gates G1, G2, and G4 map to these batches.

## Enforced rules (hooks)

| Rule | What it blocks |
| --- | --- |
| `human-owned` | agent writes to `.harness/policy.json` and to approval or manual-check records |
| `approval-required` | tracker/SCM writes and `git push` without an open approval window |
| `protected-items` | any write, link, or child on a protected work item, even with approval |
| `tests-with-code` | commits that change source files with no test change in the commit or on the branch |
| `generated-files` | hand edits to generated files |
| `guarded-paths` | commits to guarded paths without check or manual evidence for the staged tree |
| `draft-reviewed-prs` | non-draft pull requests; pull requests without a `ready` verdict and passing checks for HEAD; publishing drafts or voting |
| workflow | branch naming with exactly one work-item key, in-progress state, spec before code, completion evidence, protected branches, stack merge order |

When a hook blocks you, read its reason and fix the cause. Never retry through another tool or
route around it.

## Models per stage

| Stage | Where it runs | Model |
| --- | --- | --- |
| Backlog, spec, review synthesis | main session | the strongest model available (Opus-class), high effort |
| Architect candidates | design subagents | same as the main session |
| Implementation | main session | Opus-class at medium effort, or Sonnet-class; measure both on real Stories |
| Thermos reviewers | `agents/thermo-*` | pinned `model: opus` |

## Evidence of the run

Keep a short running record in the session: each gate's approval id, each created work item id,
each commit per Task, check evidence paths, and the verdict, so anyone can audit the run later.
