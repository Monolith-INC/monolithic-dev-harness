# Feature and Epic Fan-out

Reference for `generate-breakdown-work-items` PHASE 5. Reuses intake `destination` and
`language`. Invokes the per–User Story workflow (PHASE 1–4) once per child Story.

## When to fan out

After intake confirmation, PHASE 1 resolves the work item type:

| Type | Action |
| --- | --- |
| User Story | Single-story path (PHASE 1–4); no fan-out |
| Feature | Fan-out across child User Stories |
| Epic | Fan-out across User Stories under child Features |
| Other | STOP — unsupported |

## Discover children first

**Identify every child User Story before processing any of them.** Build the full list, present
a short inventory to the user, then start the loop.

### Azure

1. `wit_get_work_item(id, expand=relations)` on the Feature or Epic.
2. Collect child relations / hierarchy children.
3. **Feature:** keep items with `System.WorkItemType == "User Story"` (and equivalent Story types
   if the process template uses them).
4. **Epic:** for each child Feature, load children and collect User Stories. Never attach Tasks to
   the Epic. Never treat Features as Stories.
5. Batch-read with `wit_get_work_items_batch_by_ids` when listing many ids.

### Artifacts / filesystem

1. Feature file: find tickets with `parent_id_artifacts path` / `parent_id` pointing at this
   Feature, or Tickets under a known Feature id prefix.
2. Epic: resolve child Feature files, then Stories under those Features.
3. If discovery is ambiguous → STOP and ask once for an explicit Story list or path lookup.

If **zero** child Stories → STOP with a clear message (nothing to break down).

## Selection UX (optional)

When more than one Story is found, present a **variant multi-select** of Story titles/ids
(`all` Recommended when processing everything is the default judgment; `other…` last). Process
only the selected set. Default to `all` if the user confirms without narrowing.

## Per-Story loop

For each selected User Story, **in order**:

1. Run PHASE 1 ingest for that Story (Feature body + Story body + verbatim ACs).
2. Run PHASE 2 — save Implementation Plan (must succeed before Tasks).
3. Run PHASE 3–4 — decompose and persist Tasks using the **same** intake `destination` and
   `language` (do not re-prompt).
4. Record a per-Story result: `success` | `failed` + error message + `plan_path` / Task ids.

### Failure isolation

- One Story's failure **must not** silently skip the remaining Stories.
- On failure: log the error, mark that Story `failed`, **continue** with the next Story.
- Do not abort the entire fan-out unless the user asks to stop, or a fatal shared fault occurs
  (artifacts path unwritable, Azure auth lost).

## Final report

After the loop, print a table-like summary:

```text
Fan-out complete for <Feature|Epic> <id/path>
destination=<…> language=<…>

OK   <story> → plan=<path> tasks=<n>
FAIL <story> → <error>
…
Processed N · Succeeded S · Failed F
```

If `F > 0`, exit the run as **partial failure** (do not claim full success).

## Out of scope

- Creating intervening Features under an Epic
- Estimating points at Feature/Epic level
- Rewriting Story acceptance criteria
