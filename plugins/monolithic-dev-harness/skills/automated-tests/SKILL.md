---
name: automated-tests
description: Create and run automated tests for workflow and policy changes.
---

# Automated tests

Add regression coverage for new policy, adapter, and installer behavior before finishing a task.

## In the harness

In a user's project, this means tests for the behavior the Story changes: the settings'
`tests_required` pairs source paths with the tests that must change with them, and completion
waits for them.
