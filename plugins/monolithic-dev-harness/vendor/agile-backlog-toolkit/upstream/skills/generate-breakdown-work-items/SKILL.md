---
name: generate-breakdown-work-items
description: >
  From a User Story (or Feature/Epic with child Stories), generate an Implementation Plan in the local artifacts and atomic child Tasks aligned to acceptance criteria — including Staging, Review, and a Done Breakdown Task. Use when the user runs /generate-breakdown-work-items, says "break down this story into tasks", "create tasks from acceptance criteria", "breakdown work items", or provides a Story/Feature/Epic id, URL, or artifacts path and wants plan + Task children for delivery. Does not invent acceptance criteria or implement product code.
license: MIT
---

# Generate Breakdown Work Items

Conductor for turning Story acceptance criteria into a artifacts path Implementation Plan and atomic
child Tasks. Load references as each phase needs them — this file is the score, not the textbook.

References (skill-specific, in `./references/`):

- `./references/intake-ux.md` — prompt order, invariant/variant lists, `all` / `other` / `Recommended`
- `./references/plan-generation.md` — Feature+Story ingest, AC coverage, artifacts path Implementation Plan
- `./references/atomic-tasks.md` — atomic Tasks, Staging/Review/Breakdown, destination writers
- `./references/fan-out.md` — Feature/Epic child discovery, per-Story loop, failure isolation

Shared references (in `../../references/`):

- `azure-mechanics.md` — MCP calls, linking gotchas, URL→id
- `ticket-structure.md` — local draft constraints
- `decomposition-rules.md` — hierarchy (Epic → Feature → Story → Task)

Resolve the artifacts path with `bin/agile-backlog-toolkit config --show`, which reads
`.agile-backlog-toolkit/config.json` and falls back to older locations. See
`../../references/project-config.md`.

**Not in scope:** inventing or rewriting acceptance criteria; Feature-level story-point estimation;
implementing the product under breakdown — only plan + work-item persistence.

---

## PHASE 0 — INTAKE (selection only)

Read `./references/intake-ux.md` before prompting. Gather inputs **one at a time**.

| Input | Required | Purpose |
| --- | --- | --- |
| `work_item_ref` | yes | Azure ID, URL, or artifacts path/filesystem path to Story, Feature, or Epic |
| `destination` | yes | `filesystem` \| `azure` \| `both` \| `other:…` |
| `language` | no | `en` (default when omitted) \| `pt-BR` \| `other:…` |

Also accept flags from `/generate-breakdown-work-items` or conversational inference.

### Rules (must follow `intake-ux.md`)

1. If `work_item_ref` is missing → STOP and ask before continuing.
2. If `destination` is missing → show the invariant destination list (with `other…` last; apply
   `Recommended` when judgment requires it).
3. If `language` is missing → set `en` (do not force a prompt).
4. Every selectable list ends with `other (inform or describe)`.
5. Variant multi-select lists include `all`.
6. Judgment calls: first option tagged `Recommended`.

### Confirmation gate

Present the normalized intake record and **WAIT** for explicit confirmation. Do **not** read
work-item bodies, write the Artifacts, or call Azure write APIs in this phase.

```text
{
  work_item_ref:   string
  source_kind:     "id" | "url" | "path"
  destination:     "filesystem" | "azure" | "both" | "other:<text>"
  language:        "en" | "pt-BR" | "other:<text>"
}
```

On confirmation, proceed to PHASE 1.

---

## PHASE 1 — INGEST

Read `./references/plan-generation.md` § PHASE 1.

1. Resolve `work_item_ref` to a work item (Azure id/url or artifacts path/filesystem path).
2. If type is **Feature** or **Epic**: go to PHASE 5 (fan-out). Do not draft a parent-level plan.
3. If type is **User Story**: read the **parent Feature body** and the **Story body** before any
   plan drafting. STOP if the Feature cannot be resolved or if acceptance criteria are missing.
4. Extract `acceptance_criteria` **verbatim** (en/pt-BR section labels per
   `../../references/ticket-structure.md`). Never invent or rewrite ACs.

---

## PHASE 2 — IMPLEMENTATION PLAN

Read `./references/plan-generation.md` § PHASE 2.

1. Draft a plan that **addresses every** acceptance-criteria entry.
2. Write it to `<artifacts>/Implementation_Plans/YYYY-MM-DD-<story-slug>.md` with the frontmatter
   contract in `plan-generation.md`.
3. Re-read the file; record `plan_path` on the run context; present path + summary.
4. **Do not create Tasks** in this phase. If PHASE 3 is invoked without a saved `plan_path` on
   disk → STOP: "Implementation Plan not saved; refusing Task creation."

Optional: WAIT for user accept/edit of the plan before PHASE 3.

---

## PHASE 3 — DECOMPOSE TASKS

Read `./references/atomic-tasks.md` § Task list construction.

1. Refuse to continue unless `plan_path` exists on disk.
2. Split the saved plan into atomic, testable Tasks (one ≈ one atomic commit).
3. Always append **Staging**, then **Review**, then **Breakdown** last.
4. Breakdown: assignee = Story assignee; state = Done.
5. Present the proposed Task list as a variant multi-select (`all`, `other…`, `Recommended` per
   `intake-ux.md`) and WAIT for selection before PHASE 4.

---

## PHASE 4 — PERSIST

Read `./references/atomic-tasks.md` § Persist.

1. Write selected Tasks to intake `destination` (`filesystem`, `azure`, or `both`).
2. Attach every Task as a **child of the User Story** (Azure: `wit_add_child_work_items` or
   create + link `type: "parent"`; artifacts path: parent Story ref in frontmatter).
3. Update Breakdown assignee/state; read-back assert parent + Done.
4. Report `plan_path`, Task ids/paths, and Breakdown outcome.

---

## PHASE 5 — FAN-OUT

Read `./references/fan-out.md`.

1. Enumerate **all** child User Stories under the Feature (or under Features of an Epic) **before**
   processing any Story.
2. Optionally present a variant multi-select (`all` / `other…`) of Stories to include.
3. For each selected Story: run PHASE 1–4 with the same intake `destination` and `language`.
4. On failure: record the error and **continue** remaining Stories (no silent skip).
5. End with a success/fail summary; partial failure if any Story failed.

---

## Examples

```text
/generate-breakdown-work-items --ref 12345 --destination both
→ intake confirm → Feature+Story ingest → save Implementation_Plans/…
→ propose Tasks (AC steps + Staging + Review + Breakdown) → persist to the artifacts path + Azure

/generate-breakdown-work-items --ref Features/generate-breakdown-work-items.md --destination filesystem
→ list child Stories → for each: plan + Tasks → report OK/FAIL per Story
```
