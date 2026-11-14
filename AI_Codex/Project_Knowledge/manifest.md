---
schema_version: 1
derived_from_commit: a2f686a38a25825d70e6b4a80c71f17c16315953
updated: 2026-11-14
tiers_present: [1, 2, 3, 4, 5]
---

# Project knowledge index

Built for repository review setup on 2026-11-14. Facts are indexed by catalog.tsv and expanded in small units. Counts: 18 units; {'stated': 11, 'derived': 7}. No assumed rule is recorded.

Authored policy is marked stated; tree, manifest and history observations are marked derived. The owner selected a shared store in the existing vault and private connection settings. Escalation and functional discipline were supplied as owner statements in the setup conversation. Their units have no on-disk source to invalidate them automatically.

## Retrieval

Read catalog.tsv, select by read_when, then open that unit or heading. Do not load the entire vault to answer a single review question. Unit ids are stable paths without extensions.

## Deliberate omissions and limitations

- No invented service-level commitment, support hours, incident response time, regulatory constraint or production status.
- No exact transitive dependency inventory, licence approval, coverage trend or remote CI pass-rate claim.
- No classification of current churn as technical debt: churn is a count, not a defect.
- The runtime documentation has older layout and timeout wording; conflicting claims are called out rather than silently treated as current.
- Optional review-worker and knowledge-service adapters remain uninstalled: the examined Codex worker package names unavailable model variants and does not accept the requested tool-binding flags; the knowledge installer targets .mcp.json rather than the current Codex project configuration. No adapter or dependency was installed.
- The project’s harness tracker configuration remains unchanged. Linear project P-AGE-5 is authoritative for this review configuration; legacy local tickets are not automatically migrated.

## Refresh

Compare the stored commit with current HEAD. Rebuild only derived units whose sources changed, regenerate the catalog, and leave unaffected units byte-identical. Flag stated units for human confirmation instead of overwriting them. The fixed-window churn unit must be refreshed intentionally as time moves on.
