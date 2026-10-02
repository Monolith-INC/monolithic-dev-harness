---
date: 2026-09-23
type: ticket
work_item_type: Feature
provider: local
parent_id: "pending:draft-improve-delivery-workflow-continuity-and-discovery"
language: en
tags: [ticket, feature, discovery]
---

# Enable structured product discovery before backlog drafting

## Objective

Allow the harness to document and compare product directions before a selected direction enters
backlog drafting.

## Scope

### Included

- Capture the problem, intended outcomes, constraints, assumptions, risks, and open questions.
- Compare candidate directions and hand the selected direction to backlog drafting.

### Excluded

- Automatically choosing a product direction.
- Creating tracker records before a person selects a direction.

## Success Criteria

- [ ] The Feature produces a durable discovery record before backlog drafting.
- [ ] The Feature requires a human decision before it creates or changes backlog records.

## Areas / modules involved

- `plugins/monolithic-dev-harness/skills/`
- `plugins/monolithic-dev-harness/runtime/orchestrator_core/`
- `AI_Codex/`

## Original Description

"Is there a planning/brainstorming workflow?"
