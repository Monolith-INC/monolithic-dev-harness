---
date: 2026-09-23
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-support-structured-product-discovery"
story_points: 3
language: en
tags: [ticket, user-story, discovery]
---

# Select a direction and hand it to backlog drafting

## 🎯 What

As a product team, we need the harness to move only a human-selected product direction into the
existing backlog workflow.

## 💡 Why

The team needs backlog records to represent a deliberate product decision rather than an unreviewed
option.

## 📋 Expected Behavior

```text
Discovery record
  -> human selects a direction
  -> selected outcome, constraints, and questions
  -> existing backlog drafting workflow
```

## ✅ Acceptance Criteria

- [ ] Require an explicit human selection before creating or changing backlog records.
- [ ] Pass the selected direction, intended outcome, constraints, and unresolved questions to backlog drafting.
- [ ] Preserve rejected directions in the discovery record without adding them to the backlog.
- [ ] Apply the existing approval protocol to any backlog write.

## 🔧 Technical Notes

The handoff must use the current backlog drafting workflow. It must not create tracker records,
links, or hierarchy changes before the required approval.

## 📊 Complexity

**3 points** — Largest driver: Scope=3, Uncertainty=3, Integrations=2, Data=2, QA=3, Rollout=2 → 3 points

## 📄 Original Description

"Is there a planning/brainstorming workflow?"
