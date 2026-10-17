# Finish Feature Development

With Git-based delivery. Without it, the skill's local mode applies (steps 1, 2, 7 and 8).

1. Fetch the feature work item and its children through the tracker adapter.
2. Verify every child story has required completion artifacts and logical done evidence.
3. Confirm Stories already landed into Feature via `merge-story-stack-into-feature` (or equivalent merge commits).
4. Reconcile the stack if ancestor updates are pending.
5. Only when the user wants one, open or update the feature pull request targeting the protected trunk branch via the SCM adapter.
6. Link that pull request to the feature work item.
7. Publish closeout artifacts (verification and resolution evidence) on the feature work item.
8. Request the logical `done` transition only after the closeout artifacts exist; a pull request is never a condition for done.
