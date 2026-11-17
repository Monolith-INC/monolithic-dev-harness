---
name: knowledge
description: Find and use source-backed project knowledge through a bounded retrieval ladder.
---

# Project knowledge

Use the project's selected knowledge store before relying on project-specific
conventions. Start with `harness knowledge catalog`, use `harness knowledge find
<terms>` to locate relevant sections, then `harness knowledge fetch <id>` to read
them. The CLI follows the project's configured format; do not switch stores with
`--store` when using a Markdown store.

For Markdown stores, `--anchor`, `--start-line`, `--start-column`, and
`--max-tokens` limit a fetch; `harness knowledge links <id>` shows references.
Check provenance and source evidence before treating a unit as a project rule.
Assumed knowledge is a lead, not proof. Follow any continuation when a fetch is
truncated.

## Legacy revision stores

Projects still configured for the legacy revision store keep their existing
revision history. Use `--store project` for `catalog`, `find`, `resolve`, `fetch`,
and `status`. When a legacy unit is stale or missing, first inspect its listed
sources and state the gap. If refreshing that legacy store is appropriate for
the task, use `harness knowledge refresh --store project`; refresh appends a new
revision and preserves prior revisions. Do not run `refresh` for a Markdown
store, where reads are intentionally read-only.

To convert a legacy store, run `harness knowledge migrate --destination <new-path>`
explicitly. The destination must not exist, and its parent directory must exist.
Migration copies the legacy files unchanged into the new store's `.legacy` archive,
creates searchable Markdown units for current revisions, and does not alter
settings or remove the legacy store. Inspect the new store before changing the
project's selected format. Units whose provenance cannot be mapped safely cause
the migration to fail without publishing a partial destination. Legacy history
and freshness evidence remain available in the `.legacy` archive; migrated source
freshness is treated as unknown unless its Markdown metadata supplies verifiable
fingerprints.

After Markdown is selected, use `harness knowledge catalog --legacy` (or add
`--legacy` to `find`, `resolve`, `fetch`, or `status`) to query the preserved legacy store. This
compatibility path is read-only. To initialize or refresh legacy data, first
select the legacy format again.

If the selected store is empty, stale, or silent, inspect the authoritative
source and state the gap rather than guessing. Never edit a knowledge revision,
catalog, or index by hand.
