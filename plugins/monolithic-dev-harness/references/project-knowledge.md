---
title: Project knowledge architecture and retrieval strategy
status: current
last_reviewed: 2026-10-09
---

# Project knowledge architecture

## Purpose

Project knowledge is a small, maintained routing and evidence layer between an agent and a large
codebase. It helps an agent identify which authoritative project documents matter for a decision;
it does not replace those documents or current source code.

## Information architecture

The reference `Project_Knowledge` model organizes knowledge in five tiers:

1. **Identity:** purpose, users, ownership and escalation.
2. **Structure:** architecture, topology, directory rules, domain concepts and decisions.
3. **Mechanics:** build/runtime, APIs, data, tools, testing and operations.
4. **Rules:** coding, security, compliance, workflow and non-functional constraints.
5. **Evolution:** hotspots, risks, gaps and accepted technical debt.

Each unit has one durable identity, a title, a tier and area, a `read_when` routing hint, concise
content, evidence/source locators, provenance/confidence, freshness and lineage. Explicitly unknown
facts remain open questions. Facts reported by source are distinguished from derived conclusions;
unsupported assumptions are not promoted to project rules. A catalog is a rebuildable index, not a
second source of truth.

The harness stores immutable revisions beneath `.harness/knowledge/stores/<store>/`; its catalog,
source index and lifecycle events make provenance and freshness inspectable. Querying is bounded:
`catalog` routes, `find` returns at most twelve current matches, and `fetch` loads only selected
units. The current v1 store seeds a source-backed pointer to `.harness/settings.json`. Curated units
can be added as the store's acquisition capability grows; agents must not treat an empty store as a
project failure.

## Retrieval contract

At the beginning of project-specific discovery, before broad reads/searches, the agent runs:

```sh
harness knowledge catalog --repo . --store project
harness knowledge find <specific request terms> --repo . --store project
harness knowledge fetch <returned-logical-unit-id> --repo . --store project
```

The agent cites the unit and its evidence when using it, prefers source-backed facts over derived
ones, then checks the cited current source before making code changes. It fetches only relevant
sections and records unresolved facts as questions. If the store is empty, missing, stale or
unavailable, it states that briefly and proceeds with focused repository inspection. Retrieval
never becomes a governance gate or a reason to stop.

## Ownership and maintenance

Project owners decide what knowledge is authoritative and when it should be refreshed. Discovery
may identify a missing unit, but source-backed content must be reviewed before it becomes a durable
rule. Changes create a new immutable revision; old revisions remain available for audit. Rebuild
the catalog after unit updates. Keep detailed evidence in its authoritative source and use the
knowledge store to route readers there.

## Source model

This design follows the five-tier taxonomy, catalog/find/fetch ladder, bounded results, provenance,
freshness, source citations and open-question discipline of Aplicatudo's `Project_Knowledge` model.
Those project-specific facts are not copied into this harness. Current implementation details are
verified against `plugins/monolithic-dev-harness/scripts/harness/knowledge.py` and its tests.
