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
# See active and completed task totals

## 🎯 What

Show the active and completed task totals on the task screen, with clear wording for zero, one, and multiple tasks.

## 💡 Why

People need to see unfinished and finished work without counting task rows themselves.

## 📋 Expected Behavior

The task screen shows separate active and completed totals. Each total uses clear wording for zero, one, and more than one task.

## ✅ Acceptance Criteria

- [ ] Show the number of active tasks and the number of completed tasks.
- [ ] Show sensible singular and plural labels, including when either count is zero.

## 🔧 Technical Notes

The task screen already shows the active task total. Add the completed total beside it and keep both labels clear at zero, one, and multiple tasks.

## 📊 Complexity

**3 points** — Largest driver: Scope=2, Uncertainty=2, Integrations=1, Data=1, QA=3, Rollout=1 → 3 points

## 📄 Original Description

“Show the number of active tasks and the number of completed tasks.”

“Show sensible singular and plural labels, including when either count is zero.”
