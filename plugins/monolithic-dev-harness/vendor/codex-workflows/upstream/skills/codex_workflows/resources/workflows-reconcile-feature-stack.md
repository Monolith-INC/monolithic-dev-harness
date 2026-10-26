# Reconcile Feature Stack

1. Inspect the feature and story pull requests through the SCM adapter.
2. Determine ancestor order from tracker child ordering and PR bases.
3. Merge or rebase each ancestor into descendants in order; resolve conflicts explicitly.
4. Keep story pull-request bases on the feature branch; do not open Feature→trunk during reconcile.
5. Re-run verification after each stack update.
6. Publish reconciliation evidence to the feature work item through the tracker adapter.
