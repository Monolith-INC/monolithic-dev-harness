---
date: 2026-10-05
type: ticket
work_item_type: User Story
provider: local
parent_id: "DAY-001"
story_points: 3
language: en
tags: [ticket, user-story, day-001]
---
# Update both task counts after status changes

## 🎯 What

Keep the active and completed task totals current when a task is marked done or active.

## 💡 Why

People should see the current number of unfinished and finished tasks after changing a task's status.

## 📋 Expected Behavior

Marking an active task done lowers the active total and raises the completed total. Marking a completed task active raises the active total and lowers the completed total. Both displayed values reflect the change immediately, including when either total becomes zero or one.

## ✅ Acceptance Criteria

- [ ] Update both counts when a task is marked done or active.

## 🔧 Technical Notes

This Story follows the Story that displays both task totals. The existing task list controller already updates the watched task list when a task changes status.

## 📊 Complexity

**3 points** — Largest driver: Scope=2, Uncertainty=1, Integrations=1, Data=1, QA=3, Rollout=1 → 3 points

## 📄 Original Description

“Update both counts when a task is marked done or active.”
