---
id: "2-structure/directory-conventions"
tier: 2
type: "structure"
area: "directories"
title: "Document and source locations"
read_when: "Choosing where a plan, work item, durable document or generated artifact belongs."
provenance: "stated"
sources:
  - "AGENTS.md"
  - "CONSTITUTION.md"
  - "docs/03-engineering/development.md"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[4-rules/workflow]]"
---

## Summary

The constitution assigns durable documents to their work item and distinguishes them from temporary planning notes.

## Layout

Tickets/ is the canonical local backlog under Constitution Article 8. docs/work-items/ holds durable work-item documents. AI_Codex/ is the existing project vault and includes historical records. Superpowers specifications and plans go under the ignored .superpowers/specs/ and .superpowers/plans/ folders. vendor/ holds source copies; dist/ and installed copies are generated outputs.

## Rules

Article 8a requires work-item document names to include document type, item type, number and title slug. The owner explicitly chose AI_Codex/Project_Knowledge for this shared review index; private review connection settings remain outside the shared store.

## Open questions

- Older vault and standing documents may describe retired layouts; prefer the constitution and current code when they conflict.
