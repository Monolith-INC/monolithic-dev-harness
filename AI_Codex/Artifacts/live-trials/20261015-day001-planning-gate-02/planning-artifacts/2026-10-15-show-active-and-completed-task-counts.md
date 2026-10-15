---
type: implementation-plan
feature: null
story: docs/planning/Tickets/Ready/draft-show-active-and-completed-task-counts.md
skill: generate-breakdown-work-items
language: en
destination: local
status: draft
created: 2026-10-15
---

# Implementation Plan: Show active and completed task counts

## Context

The task screen currently derives the active total from the task list before applying search and status filters. Task values already carry completion state, and the screen watches that list through Riverpod. This work adds the completed total while preserving the existing local task flow.

## Acceptance criteria coverage

1. **Given active and completed tasks, when the task screen is shown, then both full-list totals are visible.** Delivery step 1 adds the completed total alongside the active total; step 2 verifies the mixed-list display.
2. **Given either total is zero or one, when the task screen is shown, then the count and label use the correct singular or plural form.** Delivery step 1 defines both labels; step 2 checks zero, one, and plural examples for each state.
3. **Given a task is marked done or active, when the task state updates, then both totals reflect the change.** Delivery step 1 derives the values from current task state; step 2 toggles completion both ways and checks both totals.
4. **Given search or a status filter hides tasks, when the task screen is shown, then both totals still describe the full list.** Delivery step 1 keeps the counts based on the complete list; step 2 hides matching tasks through search and filters and checks the totals remain unchanged.

## Delivery steps

1. Update the count area in `lib/presentation/task_list_page.dart` to show active and completed task totals derived from the full list, with zero, singular, and plural wording. Keep visible-row filtering unchanged.
2. Add focused widget coverage in `test/presentation/task_list_page_test.dart` for mixed counts, zero and singular/plural labels, completion toggles in both directions, and count independence from search and status filters.

## Defaults

The harness will add Staging, Review, and Breakdown Tasks after the delivery Tasks. No assignee or sprint is set; the local tracker has no planning replies configured.
