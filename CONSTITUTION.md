---
title: Constitution of the monolithic-dev-harness
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-15
---

# Constitution

The settled rules for how the harness works and how work on it is done. Each one was decided by
the owner after a question came up more than once. Read this before designing, planning or changing
a workflow, and follow it over any earlier plan, design or habit that disagrees.

The details behind these rules live in
[`AI_Codex/Specs/2026-10-15-workflow-alignment.md`](AI_Codex/Specs/2026-10-15-workflow-alignment.md)
(decisions 1–12). Change an article only with an explicit owner decision, recorded here with its
date.

## Article 1 — The three sources and what each owns

The harness is assembled from three source projects. Each brings a workflow, not only skills, and
each workflow runs as its source wrote it: its phases, its approval steps, its read-backs, its
audits and its critic reviews. The harness adds no parallel mechanism for what a source owns.

| Source | Owns |
| --- | --- |
| BMad Method | Understanding the request and shaping the approach: discovery, planning, hardening, and the idea route |
| agile-backlog-toolkit | The backlog: creating, refining, splitting, sizing and breaking down Epics, Features and Stories, and each Story's implementation plan |
| codex-workflows-plugin | Delivery: starting a Story, technical specs with critic review, implementation, review, resolution, closing a Feature |

The harness itself owns the contract between them: the stages, the approval questions, the tracker
gateway and the checks that decide what may happen next.

## Article 2 — Look at the source first

Before designing anything a source already covers, read how that source does it, and follow it.
The agile-backlog-toolkit in particular has already solved the backlog questions (what refinement
is, when an item is ready, how changes reach existing items, how Stories are broken down). Do not
reason from a skill's name: read the skill before describing, placing or changing it.

Source copies: agile-backlog-toolkit at `/home/monolith/projects/agile-backlog-toolkit`;
codex-workflows-plugin at `/mnt/DATA/Projects/Personal/codex-workflows-plugin`.

## Article 3 — What refinement is

- **Refinement is about an item's text.** An item starts as a draft: its original description, or
  the raw title and requirements that `generate-work-item` writes. Refining it means working that
  description into its final version and writing it in the template for its type with
  `enrich-work-item`. In the harness, the BMad stages (discovery, planning, hardening) do the work
  of reaching the final version.
- **The templates** are the agile-backlog-toolkit's `common/templates/canonical-*.md`:
  - Story: What, Why, Expected Behavior, Acceptance Criteria, Technical Notes, Complexity, Original
    Description.
  - Feature: Objective, Scope, Success Criteria, Areas/Modules, Original Description.
  - Epic: Strategic Vision, Business Problem, Strategic Objectives, Success Metrics, Strategic
    Scope, Areas/Projects, Dependencies and Risks, Original Description.
- **The draft is never lost.** It is kept word for word in the Original Description section.
- **An item is refined when it passes `validate-artifact` for its type.** A refined item is only
  validated again, never re-enriched; only what fails validation is enriched.
- **Each item is refined on its own text.** A Feature being refined says nothing about its
  Stories. `decompose-backlog` creates the children, or only validates them when they are already
  refined.

## Article 4 — Tasks are a Story's breakdown, not a level of the hierarchy

Epics, Features and Stories form the backlog hierarchy. Tasks are the breakdown of one Story into a
sequence of steps to carry out (`generate-breakdown-work-items`), with Staging, Review and
Breakdown Tasks added at the end. A Story without Tasks has not been broken down yet; that is a
routine step, not a sign the Story is unrefined. A Story's implementation plan is saved and
approved before its Tasks are proposed.

## Article 5 — Work items are the source of truth

Plans, specs and Tasks are derived from the work items. When the approach changes, whether from the
BMad stages, a technical spec or the user, the work items are updated first (`amend-workitems` for
an Epic or Feature tree, `enrich-work-item` for one item), then the plan, then the Tasks.

## Article 6 — Show it, approve it, then save it

Every document or work item that is created is shown to the user for approval, then saved through
the selected tracker. No later approval bundles several of them together.

- Stories and Tasks are approved separately, in the toolkit's order.
- Each Story's implementation plan is approved on its own; that approval is the Story's
  `implementation-confirm`, and it precedes its Tasks.
- The harness words every approval question itself (`config/gates.toml`); the agent never
  rephrases one.

## Article 7 — Tracker writes go through the harness gateway

Every write to a tracker (local, Azure DevOps, Linear) goes through the harness gateway and is
held to an approval that covers it. Every write is read back before it is reported as done. A
skill never calls a tracker's own tools directly; when the gateway lacks an operation a source
skill needs, add it to the gateway.

The bundled local tracker is the agile-backlog-toolkit's `Tickets/` folder at the project root,
laid out as the toolkit lays it out: one ticket file per item (its front matter, its description as
the body) in `Tickets/Ready`, `Tickets/InProgress` or `Tickets/Done`. A ticket without
`provider_id` is a draft; a tracked item changes only through the gateway (owner, 2026-10-16).

## Article 8 — Plans and specs

- One implementation plan per Story: the agile-backlog-toolkit's plan, which maps every acceptance
  criterion to a step, is the Story's execution contract. There is no plan covering several
  Stories.
- `write-spec` owns technical specs (tech spec, design doc, ADR, API contract), with its critic
  review, and writes only the kinds a Story still lacks.
- `bmad-spec` writes the product-level spec on the idea route.
- BMad's Build workflow (`bmad-build`) is assimilated, not removed. Its plan file is the hardened
  approach that refinement takes as input, never a Story's implementation plan. BMad's ticket list
  (`tickets.py`) is read as input only; `Tickets/` is the only backlog (owner, 2026-10-16).

## Article 9 — Where work starts and where it may stop

- A work session tracks the item the user starts from: an Epic, a Feature or a Story.
- When that item is already refined (Article 3), the user is asked whether to rework it with the
  BMad stages or use it as it is. A draft goes through the BMad stages without asking.
- The idea route may stop at a product brief or spec; the user chooses whether to continue into
  technical discovery.

## Article 10 — Version control is optional

No harness decision depends on Git. Steps that need Git (branches, commits, pull requests, Feature
stacks) run only when the user chose Git-based delivery. Without it, a Feature is closed through
`finish-feature-development` in its local mode.

A pull request is always the user's choice, with or without Git-based delivery: it is opened only
when they ask for one and is never a condition for marking a Story, Feature or Epic done (owner,
2026-10-15).

## Article 11 — No compatibility paths, no dead material

The harness is not in production. When something is replaced, the old version is removed in the
same change: code, configuration, tests and documents. No migration paths, no fallbacks for old
formats, no "superseded" notes left beside the replacement. Obsolete documents are refactored to
the current state or deleted; records of what happened (trial evidence, transcripts) stay as
records.

## Article 12 — Say what things are

In documents, plans and replies, pair every skill, command, stage or file name with what it does,
in plain words. Never assume the reader knows a name.
