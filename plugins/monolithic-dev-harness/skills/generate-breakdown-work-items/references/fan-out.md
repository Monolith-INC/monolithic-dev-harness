# Feature and Epic Fan-out

Reference for `generate-breakdown-work-items` fan-out. Reuses the selected tracker destination and
effective language. Invokes the per–User Story workflow once per child Story.

## When to fan out

After reference resolution, inspect the work item type:

| Type | Action |
| --- | --- |
| User Story | Single-story path (PHASE 1–4); no fan-out |
| Feature | Fan-out across child User Stories |
| Epic | Fan-out across User Stories under child Features |
| Other | STOP — unsupported |

## Discover children first

**Identify every child User Story before processing any of them.** Build the full list, present
a short inventory to the user, then start the loop.

### Selected tracker

1. Load the Feature or Epic through the selected tracker adapter.
2. Collect normalized child relationships.
3. **Feature:** keep items whose normalized kind is User Story.
4. **Epic:** for each child Feature, load children and collect User Stories. Never attach Tasks to
   the Epic. Never treat Features as Stories.
5. Use the provider's batch-read operation when it has one.

### Artifacts / filesystem

1. Feature file: find tickets with `parent_id_artifacts path` / `parent_id` pointing at this
   Feature, or Tickets under a known Feature id prefix.
2. Epic: resolve child Feature files, then Stories under those Features.
3. If discovery is ambiguous → STOP and ask once for an explicit Story list or path lookup.

If **zero** child Stories → STOP with a clear message (nothing to break down).

## Selection UX (optional)

When more than one Story is found, process the full discovered set unless the user requested a
narrower scope. Show that scope with the final review batch; ask only if the intended set is unclear.

## Per-Story loop

For each selected User Story, **in order**:

1. Run PHASE 1 ingest for that Story (Feature body + Story body + verbatim ACs).
2. Run PHASE 2 — save Implementation Plan (must succeed before Tasks).
3. Draft Tasks and add them to the combined review batch, using the same selected tracker and
   language. Publish after preflight and approval; do not re-prompt per Story.
4. Record a per-Story result: `success` | `failed` + error message + `plan_path` / Task ids.

### Failure isolation

- One Story's failure **must not** silently skip the remaining Stories.
- On failure: log the error, mark that Story `failed`, **continue** with the next Story.
- Do not abort the entire fan-out unless the user asks to stop, or a fatal shared fault occurs
  (artifacts path unwritable, selected tracker authentication lost).

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
