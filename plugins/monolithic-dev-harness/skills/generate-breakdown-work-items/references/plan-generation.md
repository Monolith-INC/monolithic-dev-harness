# Implementation Plan Generation

Reference for `generate-breakdown-work-items` PHASE 1 (ingest) and PHASE 2 (plan).
Depends on a confirmed intake record from `./intake-ux.md`.

**Hard rule:** Save the Implementation Plan to the local artifacts **before** any Task is created.
PHASE 3+ must refuse to run until the plan file exists on disk.

## PHASE 1 — Ingest

### Resolve the target

From intake `work_item_ref` / `source_kind`:

| `source_kind` | Resolution |
| --- | --- |
| `id` | `tracker_get_work_item(ref=<id>)` |
| `url` | Extract the id with the tracker's `ids` patterns (`tracker_describe`), then same as `id` |
| `path` | Read the markdown file; parse frontmatter + body |

Determine `work_item_type`:

- Tracker: the item's `kind` (`user_story` | `feature` | `epic` | …)
- Artifacts: frontmatter `work_item_type` / `type: feature` / Feature folder / ticket sections

**Branch:**

- **User Story** → continue ingest below, then PHASE 2.
- **Feature or Epic** → hand off to fan-out (`./fan-out.md`). Do **not** invent a plan for the parent itself.
- Anything else → STOP and report unsupported type.

### User Story ingest (required reads)

Load both before drafting the plan:

1. **Parent Feature body** (only when the Story has a parent)
   - Tracker: `tracker_get_work_item` on the Story's `parent_id`
   - Files: `parent_id`, or the Feature path from frontmatter / links
   - A Story with no parent is valid: plan from the Story alone. STOP and ask once only when the
     Story names a parent that cannot be read.
2. **User Story body** — title, description/sections, assignee when present

Capture a normalized record:

```text
{
  story: {
    id_or_path: string
    title: string
    body: string
    assignee: string | null
    acceptance_criteria: string[]   // verbatim lines; never invent
    provider_id: number | null
    source: "artifacts path" | "azure" | "filesystem"
  }
  feature: {
    id_or_path: string
    title: string
    body: string
    provider_id: number | null
  }
  language: "en" | "pt-BR" | "other:<text>"   // from intake
}
```

### Acceptance criteria extraction

Do **not** invent or rewrite ACs.

1. Prefer the Acceptance Criteria section:
   - en: `✅ Acceptance Criteria`
   - pt-BR: `✅ Critérios de Aceite`
2. Split on checkbox lines (`- [ ]` / `- [x]`) or numbered/bulleted items inside that section.
3. Tracker: parse the same section from the item's `description` markdown.
4. If the section is **missing or empty** → STOP. Report that breakdown requires existing ACs; do not fabricate them.

Store each AC as a **verbatim** string (trim whitespace only).

---

## PHASE 2 — Draft and save the plan

### Coverage rule

The Implementation Plan must **address every** entry in `acceptance_criteria`. Each AC maps to at
least one plan step or checklist item. Extra clarifying steps are allowed; dropping an AC is not.

### Plan content (language from intake)

Write prose and headings in intake `language` (`en` default). Suggested structure:

1. Title — Implementation Plan for `<story title>`
2. Context — one short paragraph from Feature + Story (WHAT, not invented HOW)
3. Acceptance criteria coverage — ordered list; each item cites the verbatim AC and the planned work to satisfy it
4. Delivery steps — ordered, atomic-commit-sized steps (one self-contained, testable change each) that will later become Tasks
5. Defaults note — Staging, Review, and Breakdown Tasks will be added in Task decomposition (do not create those Tasks here)

Do not create Task work items in this phase.

### Artifacts path and frontmatter

**Path:** `harness document path --type implementation-plan --item <story key>`, in the Story's
folder (`../../../references/document-layout.md`). One plan per Story: when the file exists, revise
it rather than writing a second one. If the settings name no artifacts path, run the bootstrap
skill; never guess a location.

**Frontmatter:**

```yaml
---
type: implementation-plan
feature: <feature id or artifacts path>
story: <story id or artifacts path>
source_digest: <value from `harness plan source <story key>`>
skill: generate-breakdown-work-items
language: en   # or pt-BR
status: draft
created: YYYY-MM-DD
---
```

`status` is allowed here (plans are not ticket files). Keep `draft` until the user approves the
plan (`implementation-confirm`), then set `active`. The approval pins the plan's content; its
`status` line is not part of it, so only a change elsewhere needs a new approval.

### Save gate

1. Write the file to disk.
2. Re-read the file and assert it exists and is non-empty.
3. Record `plan_path` on the run context.
4. Have the plan approved, as the skill's PHASE 2 describes (`implementation-confirm`).

**STOP before Task creation:** PHASE 3 must check `plan_path` exists. If missing → STOP with
"Implementation Plan not saved; refusing Task creation."

### Approval

The approval is required: no Task is drafted until the plan is approved as it reads now. The plan
must identify the current Story `source_digest` from `harness plan source <story key>`. Refinement
publishes reviewed work-item content and verifies tracker readback before this plan can be approved.
If source requirements change, refresh the digest and obtain approval again. Edits must still cover
every AC.
