---
date: 2026-10-05
type: ticket
work_item_type: User Story
provider: local
parent_id: "DAY-001"
story_points: 2
language: en
tags: [ticket, user-story, day-001]
---
# Keep task counts independent of search and status filters

## 🎯 What

Keep both task totals based on the full task list when search or a status filter changes the visible rows.

## 💡 Why

People should still see the full active and completed totals while looking at only part of the task list.

## 📋 Expected Behavior

Changing the search text or switching between All, To do, and Done changes which rows are visible. The active and completed totals continue to describe the full task list.

## ✅ Acceptance Criteria

- [ ] Counts describe the full task list, not only the current search or filter results.

## 🔧 Technical Notes

This Story depends on the Story that displays both totals. The screen already keeps the watched full task list separate from the rows filtered for display.

## 📊 Complexity

**2 points** — Largest driver: Scope=2, Uncertainty=2, Integrations=1, Data=1, QA=2, Rollout=1 → 2 points

## 📄 Original Description

“Counts describe the full task list, not only the current search or filter results.”
