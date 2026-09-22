# Finish Feature Development

1. Fetch the feature work item and its children through the tracker adapter.
2. Verify every child story has required completion artifacts and logical done evidence.
3. Confirm Stories already landed into Feature via `merge-story-stack-into-feature` (or equivalent merge commits).
4. Reconcile the stack if ancestor updates are pending.
5. Open or update the feature pull request targeting the protected trunk branch via the SCM adapter.
6. Link the feature pull request to the feature work item.
7. Publish closeout artifacts (verification and resolution evidence) on the feature work item.
8. Request the logical `done` transition only after artifacts and PR linkage exist.
