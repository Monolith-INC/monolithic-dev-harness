---
type: spec
work_item_type: User Story
ticket: null
area: task-list
stack: [Flutter, Riverpod, flutter_test]
tags: [spec, user-story]
created: 2026-10-15
source: [context7, https://github.com/flutter/website/blob/main/sites/docs/src/content/cookbook/testing/widget/introduction.md]
---

# Show active and completed task counts — Work Item Spec

## Problem / need

The task screen shows how many tasks remain active, but it does not show how many are completed. Showing both totals will let people understand the full state of their task list at a glance.

## Technical details to preserve

- The task screen displays both active and completed task counts.
- Counts refer to the full task list, independently of search and status filters.
- Both counts respond when a task changes completion state.
- Labels handle zero, singular, and plural counts.

## Expected behavior (draft)

- Derive both totals from the existing task list state.
- Keep search and status filters limited to visible task rows.
- Rebuild the displayed totals when task completion changes.

## Tech stack

Flutter and Riverpod are already used by the task screen. Focused screen verification can use Flutter's `testWidgets`, text finders, and `WidgetTester` interactions.

## Research summary

Context7 `/flutter/website` documents widget tests that build a screen with `pumpWidget`, locate rendered labels with `find.text`, perform user interactions with `WidgetTester`, and pump again to observe state changes. This supports focused verification of displayed counts and completion toggles; it does not require an application architecture change.

## Acceptance criteria (draft)

- [ ] Given active and completed tasks, when the task screen is shown, then both full-list totals are visible.
- [ ] Given either total is zero or one, when the task screen is shown, then the count and label use the correct singular or plural form.
- [ ] Given a task is marked done or active, when the task state updates, then both totals reflect the change.
- [ ] Given search or a status filter hides tasks, when the task screen is shown, then both totals still describe the full list.

## References

- Project request and acceptance checks: `backlog/DAY-001-task-counts.md`.
- Context7 `/flutter/website`: <https://github.com/flutter/website/blob/main/sites/docs/src/content/cookbook/testing/widget/introduction.md>.

## Open questions

None.

## Original description

I can see how many tasks I still need to do, but I also want to see how many I have finished. Show both counts on the task screen.
