# Atomic Task Decomposition and Persist

Reference for `generate-breakdown-work-items` PHASE 3 (decompose) and PHASE 4 (persist).
Requires a saved Implementation Plan from `./plan-generation.md` (`plan_path` on disk).

## Preflight

1. Assert `plan_path` exists and is non-empty. If not → STOP:
   `Implementation Plan not saved; refusing Task creation.`
2. Re-read the plan and the Story's verbatim `acceptance_criteria`.
3. Reuse intake `language`. The destination is the selected tracker.

## Atomic-commit definition

Each AC-derived Task must be:

- **Atomic** — one self-contained change to the project
- **Testable** — can be verified with a unit test (or an equally narrow automated check)
- **Scoped** — maps to a single delivery step from the Implementation Plan (or a clear sub-step)

Do not merge unrelated plan steps into one Task. Do not invent scope beyond the plan / ACs.

## Task list construction (PHASE 3)

Build an ordered list:

1. **AC / plan Tasks** — one Task per atomic plan step that delivers AC coverage  
2. **Staging** — always append (default)  
3. **Review** — always append (default)  
4. **Breakdown** — always last (default)

### Default Tasks

| Title | Required | Notes |
| --- | --- | --- |
| Staging | yes | Prepare/verify environment or staging for the Story's delivery |
| Review | yes | Review the Story's delivered work against acceptance criteria |
| Breakdown | yes (last) | Signals breakdown complete; see Breakdown rules below |

Titles may be localized when `language` is `pt-BR` (e.g. `Staging` / `Review` / `Breakdown` kept as
proper names, or host-preferred equivalents — stay consistent within a run). Descriptions follow
`language`.

### Breakdown rules

- Title: `Breakdown` (or localized equivalent; keep recognizable)
- **Assignee** = User Story assignee (the gateway copies it when the Task is created).
  If the Story has no assignee → leave unassigned and note in the run summary; still set Done.
- **State** = Done, set with `tracker_transition_work_item` once the Tasks are read back
- Always the **last** Task in the list

### Task approval

Before persisting, write the proposed Tasks as drafts, show them, and ask `harness decision present
--gate publish-items` with the drafts as `--artifact`s. When the user's own words drop or change a
Task, change the drafts and ask again. If they drop Staging, Review, or Breakdown → WARN and re-add
them unless they explicitly confirm the omission (prefer asking again over silently dropping them).

### Effort hours per Task

A Task with no remaining hours contributes nothing to the assignee's capacity bar or the burndown
chart — it is invisible to the tooling that shows whether their sprint fits.

Once the Task list is settled, **compute the estimates — do not reason them out.** The arithmetic
is deterministic and lives in the orchestrator, so the same Story always yields the same hours.

1. **Fetch the sprint context** and save it as one JSON object: one entry per reply the selected
   tracker lists under `planning.replies` in `tracker_describe`, fetched as each entry describes
   (so existing commitments count). A tracker that lists none reads its own files; pass
   `iteration_ref` so it knows which sprint.
2. **Write the Task list** as JSON: `story_id`, `story_points`, `assignee`, `iteration_ref`, and
   `tasks[]` of `{id, title, current_hours}`. Pass a `weight` per Task only when the Implementation
   Plan says one is materially larger; otherwise the role default applies.
3. **Run it:**

```bash
bin/agile-backlog-toolkit estimate-breakdown --input <tasks>.json --replies <sprint>.json
```

Exit codes: `0` estimated and fits, `2` **blocked** (see below), `1` could not run.

The command prints the per-Task figures, the assignee's remaining capacity, and the exact field
writes to apply — it writes nothing itself. Apply the printed `write_ops` in PHASE 4.

Estimates are **applied, not negotiated** — they derive from the Story's points, so there is
nothing for a person to approve item by item. What is not optional is telling them: relay the
command's change report verbatim, naming every Task whose hours were set or changed.

**Task weights.** `Breakdown` is a completion marker and carries **no hours**; `Staging` and
`Review` take a lighter share than implementation work. That is handled automatically from the
Task titles — override with an explicit `weight` only when you have read the plan and know better.

### Capacity is a ceiling

When the derived hours exceed what the assignee has left, **STOP before writing anything** and ask
for a decision. Do not scale the numbers down to fit — that would misrepresent how long the work
takes.

```
BLOCKED — exceeds remaining capacity by 75h.
Choose one before anything is written:
  - split the Story so part of it moves to a later sprint
  - move the whole Story to a later sprint
  - reassign it to someone with capacity left
  - reduce the Task scope, then recompute
```

If the assignee cannot be matched to a team member, or the Story is unassigned, capacity is
unknown: report that plainly and proceed. Absence of data is not a failure.

### Recompute whenever the breakdown changes

**Any change to the work a Story needs invalidates its Task hours.** Tasks added, removed,
retitled, or rescoped all mean the split no longer reflects reality — and a burndown charting a
plan nobody follows is worse than one charting nothing.

So on every such change: recompute, write the new figures, and report the difference.

```
* Wire the form:      4h → 6h
* Validation rules:   4h → 6h
  Tests:              2h = 2h
  3 estimate(s) changed and were updated.
```

The capacity ceiling applies to the recomputed total as well: if the change pushes the Story past
the assignee's remaining hours, STOP and ask as above.

---

## Persist (PHASE 4)

Write only the approved Tasks, to the selected tracker, through the gateway (`tracker_*` tools);
never call a tracker's own tools. With the local tracker, each Task becomes a ticket file under
`Tickets/` (`../../../references/ticket-structure.md`).

1. Parent must be the **User Story** (never the Feature or Epic).
2. Run `harness tracker preflight` before the first write; anything it reports missing goes into
   the reviewed batch.
3. Create each Task with `tracker_create_work_item` (`kind: "task"`, `parentRef` the Story, title,
   Markdown description). The gateway gives it the Story's sprint and assignee.
4. Apply the printed hour writes with `tracker_update_work_item` (`hours`, with
   `firstEstimate: true` on a Task's first figure) where `tracker_describe` lists hour fields;
   otherwise report that the tracker keeps no hours. Report each figure written.
5. **Read-back** every created Task with `tracker_get_work_item`: assert its parent is the Story;
   for any Task given hours, assert they match what was computed. Failed assertion → STOP.
6. Set the Breakdown Task Done with `tracker_transition_work_item` and read it back.

If the gateway cannot represent a required field or operation, stop and report the gap.

---

## Run summary

After persist, report:

- `plan_path`
- Task titles and their tracker keys
- Breakdown assignee + state
- Hours written per Task, with provenance, and **every figure that changed** (old → new) — nothing
  was asked for approval, so nothing may move silently
- The assignee's remaining capacity and whether the Story fit inside it
- Any skipped `other:…` follow-ups still open
