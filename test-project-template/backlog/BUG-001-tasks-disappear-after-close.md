# BUG-001: Tasks disappear after the app closes

**Kind:** Bug report
**Size:** Unknown
**State:** Triage; reproduce and confirm expected behavior first

## Report

“A task I added was gone when I opened Daybook again.”

## Reproduction to check

1. Open the app and sign in with the displayed demo account.
2. Add a task with a distinctive title.
3. Close and reopen the app.
4. Check whether the task is still present.

## Evidence already in the repository

The current app keeps tasks in memory and starts with sample tasks after a restart. The current product notes describe that as a prototype limit. The harness should confirm this behavior and determine whether the product owner now expects tasks to be saved before treating it as a defect.

## Next step

If saving tasks is now expected, reclassify this as a persistence feature and compare storage choices. If the current local-only behavior is still intended, close the report as expected behavior. Do not silently add storage based on this report alone.
