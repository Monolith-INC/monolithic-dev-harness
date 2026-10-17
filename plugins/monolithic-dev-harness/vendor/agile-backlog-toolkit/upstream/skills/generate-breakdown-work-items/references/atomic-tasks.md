# Atomic Task Decomposition and Persist

Reference for `generate-breakdown-work-items` PHASE 3 (decompose) and PHASE 4 (persist).
Requires a saved Implementation Plan from `./plan-generation.md` (`plan_path` on disk).

## Preflight

1. Assert `plan_path` exists and is non-empty. If not → STOP:
   `Implementation Plan not saved; refusing Task creation.`
2. Re-read the plan and the Story's verbatim `acceptance_criteria`.
3. Reuse intake `destination` and `language`. Do not re-prompt unless a value is incomplete
   `other:…`.

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
- **Assignee** = User Story assignee (`System.AssignedTo` on Azure; frontmatter metadata if present).
  If the Story has no assignee → leave unassigned and note in the run summary; still set Done.
- **State** = Done (Azure: set `System.State` to the project's Done/Closed equivalent for Task;
  artifacts path: mark status Done in the draft body/frontmatter convention used for Tasks)
- Always the **last** Task in the list

### Variant selection UX

Before persisting, present the proposed Task titles as a **variant multi-select** list
(see `./intake-ux.md`):

- Include `all` (Recommended when the full set is the default judgment)
- Include every proposed Task title
- End with `other (inform or describe)`

Wait for selection. If the user deselects Staging, Review, or Breakdown → WARN and re-add them
unless they explicitly confirm omission (defaults are mandatory per Feature ACs; prefer STOP and
re-prompt over silently dropping them).

### Effort hours per Task

A Task with no `RemainingWork` contributes nothing to the assignee's capacity bar or the burndown
chart — it is invisible to the tooling that shows whether their sprint fits.

Once the Task list is settled, **compute the estimates — do not reason them out.** The arithmetic
is deterministic and lives in the orchestrator, so the same Story always yields the same hours.

1. **Fetch the sprint context** through MCP and save it as one JSON file:
   - `work_list_team_iterations` with `timeframe: "current"` → `iteration`
   - `work_get_team_capacity` for that iteration → `capacities`
   - `work_get_team_settings` → `team_settings`
   - `wit_get_work_items_for_iteration` → `work_items` (so existing commitments count)
2. **Write the Task list** as JSON: `story_id`, `story_points`, `assignee`, `iteration_ref`, and
   `tasks[]` of `{id, title, current_hours}`. Pass a `weight` per Task only when the Implementation
   Plan says one is materially larger; otherwise the role default applies.
3. **Run it:**

```bash
bin/agile-backlog-toolkit estimate-breakdown --input <tasks>.json --payloads <sprint>.json
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

Write only the selected Tasks to intake `destination`.

### Filesystem / artifacts path

When `destination` is `filesystem` or `both`:

1. Write one markdown draft per Task under the artifacts path (prefer `Tickets/Ready/` or a host Task folder).
2. Filename pattern per `../../references/ticket-structure.md`:
   `task-<kebab-title>` is invalid as a bare prefix — use `task-<slug>` only if the host regex
   allows `task-`; otherwise `<story-id-or-0000>-task-<slug>.md` matching
   `^(\d+|tech-debt|bug|task|spike)-[a-z0-9-]+`.
3. Frontmatter: `type: ticket`, `work_item_type: Task`, parent Story ref, `language`, no `status:`
   key in Tickets/ (lifecycle note for Breakdown Done can live in the body: `State: Done`).
4. Body: title heading + short description (WHAT for this atomic unit) + link/ref to `plan_path`
   and parent Story.

### Azure Task board

When `destination` is `azure` or `both`:

1. Parent must be the **User Story** id (never Feature/Epic).
2. Prefer `wit_add_child_work_items` with `workItemType: "Task"`, `parentId: <storyId>`,
   `items: [{ title, description, format: "Markdown" }, …]` for the AC/plan + Staging + Review
   batch when possible.
3. For **Breakdown** (or any Task needing assignee/state): create as child, then
   `wit_update_work_item` to set:
   - `/fields/System.AssignedTo` → Story assignee (when present)
   - `/fields/System.State` → Done (or project-specific completed state for Task)
4. For **every Task**, `wit_update_work_item` to set:
   - `/fields/Microsoft.VSTS.Scheduling.RemainingWork` → hours (drives capacity + burndown)
   - `/fields/Microsoft.VSTS.Scheduling.OriginalEstimate` → hours — **Agile/CMMI only.** This
     field does not exist on Scrum projects and writing it there fails silently. When the process
     is unknown, write only `RemainingWork`, which every process has.
   - `/fields/Microsoft.VSTS.Common.Activity` → activity, when one can be determined. Allowed
     values are configured per project — read them rather than assuming, and leave it unset when
     unsure. (`Discipline` on CMMI.)
   Apply to every Task. Report each figure written; see 'Effort hours per Task' above.
5. Set `/fields/System.IterationPath` explicitly from the parent Story rather than relying on the
   project default, so Tasks land in the sprint their Story belongs to.
6. Alternative: `wit_create_work_item` + `wit_work_items_link` with **`type: "parent"`**
   (Story is parent of Task). Never omit `type` (defaults to Related).
7. **Read-back** every created Task: assert parent is the Story id; for Breakdown assert Done and
   assignee match; for any Task given hours assert `RemainingWork` matches what was computed.
   Failed assertion → STOP.

### Shared Azure notes

Extend behavior from `../../references/azure-mechanics.md`. Parent of a Task is the **User Story**,
not the Feature. Description format: Markdown.

---

## Run summary

After persist, report:

- `plan_path`
- Task titles + destinations (artifacts paths and/or Azure ids)
- Breakdown assignee + state
- Hours written per Task, with provenance, and **every figure that changed** (old → new) — nothing
  was asked for approval, so nothing may move silently
- The assignee's remaining capacity and whether the Story fit inside it
- Any skipped `other:…` follow-ups still open
