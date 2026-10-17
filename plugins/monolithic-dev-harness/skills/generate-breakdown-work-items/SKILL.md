---
name: generate-breakdown-work-items
description: >
  From a User Story (or Feature/Epic with child Stories), generate an Implementation Plan in the local artifacts and atomic child Tasks aligned to acceptance criteria — including Staging, Review, and a Done Breakdown Task. Use when the user runs /generate-breakdown-work-items, says "break down this story into tasks", "create tasks from acceptance criteria", "breakdown work items", or provides a Story/Feature/Epic id, link, or path and wants plan + Task children for delivery. Does not invent acceptance criteria or implement product code.
license: MIT
---

# Generate Breakdown Work Items

Conductor for turning Story acceptance criteria into an Implementation Plan in the artifacts path and atomic
child Tasks. Load references as each phase needs them — this file is the score, not the textbook.

References (skill-specific, in `./references/`):

- `./references/intake-ux.md` — prompt order, invariant/variant lists, `all` / `other` / `Recommended`
- `./references/plan-generation.md` — Feature+Story ingest, AC coverage, artifacts path Implementation Plan
- `./references/atomic-tasks.md` — atomic Tasks, Staging/Review/Breakdown, writing them to the tracker
- `./references/fan-out.md` — Feature/Epic child discovery, per-Story loop, failure isolation

Shared references (in `../../references/`):

- `tracker-contract.md` — the tracker gateway: `tracker_describe` and the `tracker_*` tools
- `ticket-structure.md` — local draft constraints
- `decomposition-rules.md` — hierarchy (Epic → Feature → Story → Task)

Every tracker read and write goes through the harness gateway (`tracker_*` tools); never call a
tracker's own tools. Ask `harness document path` for the plan's path
(`../../references/document-layout.md`). When the harness route runs this skill, `harness next`
names the Story; the intake below is then already settled.

**Not in scope:** inventing or rewriting acceptance criteria; Feature-level story-point estimation;
implementing the product under breakdown — only plan + work-item persistence.

---

## PHASE 0 — INTAKE (selection only)

Read `./references/intake-ux.md` before prompting. Gather inputs **one at a time**.

| Input | Required | Purpose |
| --- | --- | --- |
| `work_item_ref` | yes | Tracker id or link, or a filesystem path to a Story, Feature, or Epic |
| `language` | no | `en` (default when omitted) \| `pt-BR` \| `other:…` |

Also accept flags from `/generate-breakdown-work-items` or conversational inference.

### Rules (must follow `intake-ux.md`)

1. If `work_item_ref` is missing → STOP and ask before continuing.
2. The destination is the selected tracker (`tracker_describe`); it is never asked.
3. If `language` is missing → use the project's harness language (do not force a prompt).
4. Ask every question with `harness decision present`; never in your own words.

### Confirmation gate

When the skill runs outside the harness route, present the normalized intake record and **WAIT**
for explicit confirmation. Do **not** read work-item bodies or write anything in this phase.

```text
{
  work_item_ref:   string
  source_kind:     "id" | "url" | "path"
  language:        "en" | "pt-BR"
}
```

On confirmation, proceed to PHASE 1.

---

## PHASE 1 — INGEST

Read `./references/plan-generation.md` § PHASE 1.

1. Resolve `work_item_ref` to a work item (`tracker_get_work_item`, or read a filesystem path).
2. If type is **Feature** or **Epic**: go to PHASE 5 (fan-out). Do not draft a parent-level plan.
3. If type is **User Story**: read the **parent Feature body** (when it has one) and the **Story
   body** before any plan drafting. A Story without a parent is valid. STOP if a named parent cannot
   be read or if acceptance criteria are missing.
4. Extract `acceptance_criteria` **verbatim** (en/pt-BR section labels per
   `../../references/ticket-structure.md`). Never invent or rewrite ACs.

---

## PHASE 2 — IMPLEMENTATION PLAN

Read `./references/plan-generation.md` § PHASE 2.

1. Draft a plan that **addresses every** acceptance-criteria entry.
2. Write it where `harness document path --type implementation-plan --item <story key>` says, with
   the frontmatter contract in `plan-generation.md`.
3. Re-read the file; record `plan_path` on the run context; present path + summary.
4. **Do not create Tasks** in this phase. If PHASE 3 is invoked without a saved `plan_path` on
   disk → STOP: "Implementation Plan not saved; refusing Task creation."

Have the plan approved before PHASE 3 (required): show it with `harness workflow show --artifact
<plan>` and put that output in your reply, then ask
`harness decision present --gate implementation-confirm --artifact <plan>`. On Revise, change the plan and ask again. Once approved,
set its `status` to `active`; editing it afterwards needs a new approval.

---

## PHASE 3 — DECOMPOSE TASKS

Read `./references/atomic-tasks.md` § Task list construction.

1. Refuse to continue unless `plan_path` exists on disk.
2. Split the saved plan into atomic, testable Tasks (one ≈ one atomic commit).
3. Always append **Staging**, then **Review**, then **Breakdown** last.
4. Breakdown: assignee = Story assignee; state = Done.
5. Write the Task drafts, show them, and ask `harness decision present --gate publish-items` with
   the drafts as `--artifact`s before PHASE 4. The user's own words in the question's Other field
   change the list; ask again for the changed list.

---

## PHASE 4 — PERSIST

Read `./references/atomic-tasks.md` § Persist.

1. Create each approved Task in the selected tracker with `tracker_create_work_item` (`kind:
   "task"`, `parentRef` the Story); the gateway gives it the Story's sprint and assignee.
2. Read every Task back with `tracker_get_work_item` and assert its parent is the Story.
3. Set the Breakdown Task Done with `tracker_transition_work_item`; read it back.
4. Report `plan_path`, Task ids/paths, and Breakdown outcome.

---

## PHASE 5 — FAN-OUT

Read `./references/fan-out.md`.

1. Enumerate **all** child User Stories under the Feature (or under Features of an Epic) **before**
   processing any Story.
2. Optionally present a variant multi-select (`all` / `other…`) of Stories to include.
3. For each selected Story: run PHASE 1–4 with the same intake `language`.
4. On failure: record the error and **continue** remaining Stories (no silent skip).
5. End with a success/fail summary; partial failure if any Story failed.

---

## Examples

```text
/generate-breakdown-work-items --ref STORY-0003
→ Feature+Story ingest → save and approve the implementation plan
→ propose Tasks (AC steps + Staging + Review + Breakdown) → approve → create in the tracker

/generate-breakdown-work-items --ref FEATURE-0002
→ list child Stories → for each: plan + Tasks → report OK/FAIL per Story
```
