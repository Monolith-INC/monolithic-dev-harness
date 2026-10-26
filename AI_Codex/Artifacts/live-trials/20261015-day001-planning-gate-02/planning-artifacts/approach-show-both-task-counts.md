---
title: Show active and completed task counts
type: planning-approach
status: draft
session_id: WS-58ca71971aca
---

# Planning approach: show both task counts

## Discovery digest

The task screen currently derives and displays the active-task total from `allTasks`, before it filters rows for search or status. Task values already expose `isComplete`, and Riverpod rebuilds the screen when the task list changes. The request is a single, cohesive display change; no new state, persistence, account, or network behavior is indicated.

## Code Map

- `lib/presentation/task_list_page.dart` — watches the complete task list, currently renders the active count, applies search/filtering separately, and handles completion toggles.
- `lib/domain/task.dart` — immutable task values and `TaskFilter`; `Task.isComplete` distinguishes active and completed tasks.
- `lib/application/daybook_providers.dart` — owns the current task list and updates it on completion changes.
- `test/domain/task_test.dart` — existing domain tests cover completion transformations; no task-screen count test currently exists.

## Proposed approach

Keep both counts derived in the task screen from the unfiltered task list. Add the completed total alongside the existing active total, with readable singular/plural labels including zero. Leave the visible task list's search and filter behavior unchanged. Verify the two totals respond when a task is marked done or active and remain based on the full list when search or filters hide rows.

## Scope and constraints

- Preserve the current in-memory task behavior and sign-in flow.
- Do not add storage, accounts, networking, or unrelated task features.
- Avoid duplicate count state; derive from the task list already watched by the screen.
- Keep the request to the task screen and focused verification for its displayed counts.

## Provisional tasks

1. Update `lib/presentation/task_list_page.dart` to display active and completed totals from the full list with zero/singular/plural wording.
2. Add focused UI coverage for both labels, count changes on completion toggles, and independence from search/filter results.

## Acceptance checks

- Given a task list, when the task screen is shown, then it displays active and completed totals for the full list.
- Given either total is zero or one, when the screen renders, then its label is sensible and grammatically singular/plural.
- Given a task is marked done or active, when the screen rebuilds, then both totals reflect the updated task list.
- Given search or a status filter hides tasks, when the screen renders, then the totals still describe the full list.

## Open questions

None identified from the request and inspected project context.

## Planning decisions

- Standard planning depth; contextual method shortlist.
- Accepted boundary sweep for zero, singular/plural, search/filter independence, and completion updates.
- Accepted critique to keep counts derived from the full task list and verify them at the screen boundary.
- Proceeded without running another elicitation method.
