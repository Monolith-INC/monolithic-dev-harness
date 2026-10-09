---
title: Project knowledge architecture and retrieval strategy
status: current
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-09
---

# Project knowledge architecture

The harness project's query contract, five-tier information architecture, provenance model,
maintenance policy and retrieval ladder are documented in the plugin's canonical reference:

[Project knowledge reference](../../plugins/monolithic-dev-harness/references/project-knowledge.md)

This design adapts the catalog/find/fetch, bounded retrieval, source-backed provenance, freshness,
and open-question practices observed in Aplicatudo's `AI_Codex_Aplicatudo/Project_Knowledge`.
It does not copy Aplicatudo's project-specific facts. The source-backed harness implementation is
`plugins/monolithic-dev-harness/scripts/harness/knowledge.py`; current behavior is verified against
its tests. The six-stage discovery handoff requires this deterministic query before broad project
reads and continues with a focused source check. Missing or stale knowledge is reported and bypassed,
never treated as a workflow blocker.
