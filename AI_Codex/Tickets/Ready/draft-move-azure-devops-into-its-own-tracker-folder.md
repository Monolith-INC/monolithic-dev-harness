---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 8
language: en
tags: [ticket, user-story, trackers, azure-devops]
---

# Move Azure DevOps into its own tracker folder

## 🎯 What

As a maintainer, I need everything Azure-specific to live in one tracker folder, so that Azure DevOps is one
tracker among several and the rest of the harness stops naming it.

## 💡 Why

Azure code and instructions are spread over at least eight places: the delivery adapter, the backlog provider,
the discovery presets, bootstrap, two hook rules, the plugin's MCP list, and eleven skills' references.

## 📋 Expected Behavior

```text
trackers/azure-devops/
  tracker.json  adapter.py  mcp.json  templates/  references/  doctor.py
  -> one adapter replaces scripts/integrations/azure.py and runtime/.../providers/azure_devops/
  -> contract tests pass unchanged
```

## ✅ Acceptance Criteria

- [ ] Create the Azure DevOps tracker folder with its manifest, adapter, MCP connection, enrichment templates, instructions, and health check.
- [ ] Replace the two Azure adapters (delivery and backlog) with the one in the folder.
- [ ] Remove Azure names from the shared code outside the folder, except the migration of existing configurations.
- [ ] Keep every existing Azure contract and integration test passing.
- [ ] Keep a repository bootstrapped on 0.1.10 working without re-running bootstrap.

## 🔧 Technical Notes

- Moves: `scripts/integrations/azure.py`, `runtime/orchestrator_core/providers/azure_devops/`, the Azure presets in
  `discovery.py`, `skills/azure-devops/`, `references/azure-mechanics.md`, `enrich-work-item/references/azure-ingest.md`.
- The harness gateway starts the tracker's MCP server; the plugin-level `.mcp.json` no longer does.

## 📊 Complexity

**8 points** — Largest driver: Scope=8, Uncertainty=3, Integrations=5, Data=3, QA=5, Rollout=5 → 8 points

## 📄 Original Description

"Trackers are adapters. You have a Linear adapter, an Azure DevOps adapter, but our tool is agnostic."
