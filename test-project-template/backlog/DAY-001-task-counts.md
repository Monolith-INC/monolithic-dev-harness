# DAY-001: Show both task counts

**Kind:** Feature request
**Size:** Short
**State:** Ready for technical investigation

## Product-owner request

“I can see how many tasks I still need to do, but I also want to see how many I have finished. Show both counts on the task screen.”

## Acceptance checks

- Show the number of active tasks and the number of completed tasks.
- Update both counts when a task is marked done or active.
- Counts describe the full task list, not only the current search or filter results.
- Show sensible singular and plural labels, including when either count is zero.

## Boundaries

- Keep the current local task behavior and sign-in flow.
- Do not add storage, accounts, or network services for this request.
- Inspect the existing count and state flow before proposing a change.
