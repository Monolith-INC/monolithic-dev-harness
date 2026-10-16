---
date: 2026-10-15
type: ticket
work_item_type: User Story
provider: local
story_points: 3
language: en
tags: [ticket, user-story, task-list]
---

# Show active and completed task counts

[[Specs/draft-show-active-and-completed-task-counts-spec.md]]

## 🎯 What

Show the number of active tasks and the number of completed tasks on the task screen.

## 💡 Why

People can already see how many tasks remain. Showing completed tasks makes the state of the full list clear without changing how the list is filtered.

## 📋 Expected Behavior

- Display active and completed totals based on the full task list.
- Keep both totals current when a task is marked done or active.
- Use suitable labels when either total is zero, one, or more than one.

## ✅ Acceptance Criteria

- [ ] Given active and completed tasks, when the task screen is shown, then both full-list totals are visible.
- [ ] Given either total is zero or one, when the task screen is shown, then the count and label use the correct singular or plural form.
- [ ] Given a task is marked done or active, when the task state updates, then both totals reflect the change.
- [ ] Given search or a status filter hides tasks, when the task screen is shown, then both totals still describe the full list.

## 🔧 Technical Notes

The task screen already watches the full task list and derives the active total before applying search and status filters. Keep the totals derived from that state rather than introducing duplicate count state.

## 📊 Complexity

**3 points** — Largest driver: Scope=2, Uncertainty=1, Integrations=1, Data=1, QA=3, Rollout=1 → 3 points

## 📄 Original Description

I can see how many tasks I still need to do, but I also want to see how many I have finished. Show both counts on the task screen.
