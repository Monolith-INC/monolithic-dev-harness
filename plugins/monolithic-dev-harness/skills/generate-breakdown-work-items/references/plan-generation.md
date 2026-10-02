# Implementation Plan Generation

Reference for `generate-breakdown-work-items` PHASE 1 (ingest) and PHASE 2 (plan).
Depends on the resolved reference and selected tracker from `./intake-ux.md`.

**Hard rule:** Save the Implementation Plan to the local artifacts **before** any Task is created.
PHASE 3+ must refuse to run until the plan file exists on disk.

## PHASE 1 — Ingest

### Resolve the target

From intake `work_item_ref` / `source_kind`:

| `source_kind` | Resolution |
| --- | --- |
| `id` | Selected tracker adapter `get_work_item(id)` |
| `url` | Extract the selected tracker's id using its contract, then `get_work_item(id)` |
| `path` | Read the markdown file; parse frontmatter + body |

Determine `work_item_type`:

- Tracker: normalized work-item kind from the selected adapter (`User Story` | `Feature` | `Epic` | …)
- Artifacts: frontmatter `work_item_type` / `type: feature` / Feature folder / ticket sections

**Branch:**

- **User Story** → continue ingest below, then PHASE 2.
- **Feature or Epic** → hand off to fan-out (`./fan-out.md`). Do **not** invent a plan for the parent itself.
- Anything else → STOP and report unsupported type.

### User Story ingest (required reads)

Load the Story, and its parent Feature when it has one, before drafting the plan:

1. **Parent Feature body** (only when the Story has a parent)
   - Tracker: follow the normalized parent relationship and load the Feature through its adapter
   - Artifacts: `parent_id_artifacts path`, `parent_id`, or Features/ path from frontmatter / links
   - A Story with no parent is valid: set `feature: null` and plan from the Story alone. STOP and
     ask once only when the Story names a parent that cannot be read.
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
    provider_id: string | null
    source: "artifacts path" | "tracker" | "filesystem"
  }
  feature: {                       // null when the Story has no parent
    id_or_path: string
    title: string
    body: string
    provider_id: string | null
  } | null
  language: "en" | "pt-BR"   // user-level preference or explicit override
  destination: ...          // selected tracker unless local-only was chosen
}
```

### Acceptance criteria extraction

Do **not** invent or rewrite ACs.

1. Prefer the Acceptance Criteria section:
   - en: `✅ Acceptance Criteria`
   - pt-BR: `✅ Critérios de Aceite`
2. Split on checkbox lines (`- [ ]` / `- [x]`) or numbered/bulleted items inside that section.
3. Tracker: parse the same section from the normalized description markdown.
4. If the section is **missing or empty** → STOP. Report that breakdown requires existing ACs; do not fabricate them.

Store each AC as a **verbatim** string (trim whitespace only).

---

## PHASE 2 — Draft and save the plan

### Coverage rule

The Implementation Plan must **address every** entry in `acceptance_criteria`. Each AC maps to at
least one plan step or checklist item. Extra clarifying steps are allowed; dropping an AC is not.

### Plan content (language from intake)

Write prose and headings in the effective harness language. Suggested structure:

1. Title — Implementation Plan for `<story title>`
2. Context — one short paragraph from Feature + Story (WHAT, not invented HOW)
3. Acceptance criteria coverage — ordered list; each item cites the verbatim AC and the planned work to satisfy it
4. Delivery steps — ordered, atomic-commit-sized steps (one self-contained, testable change each) that will later become Tasks
5. Defaults note — Staging, Review, and Breakdown Tasks will be added in Task decomposition (do not create those Tasks here)

Do not create tracker or local Task work items in this phase.

### Artifacts path and frontmatter

Resolve the artifacts root with `bin/agile-backlog-toolkit config --show`. If unset, enter guided
bootstrap to ask where plans should go and apply the reviewed setting. Never instruct manual JSON
editing or invent a directory.

**Filename:** `YYYY-MM-DD-<story-slug>.md`

- Date: run date (UTC or local host date, consistent within the run)
- `story-slug`: kebab-case from story title or id (`12345-intake-selection-ux`)
- If a file already exists for the same story today: append `-2`, `-3`, … — do not overwrite without asking

**Frontmatter:**

```yaml
---
type: implementation-plan
feature: <feature id or artifacts path; null when the Story has no parent>
story: <story id or artifacts path>
skill: generate-breakdown-work-items
language: en   # or pt-BR
destination: selected tracker  # or explicitly chosen local-only destination
status: draft
created: YYYY-MM-DD
---
```

`status` is allowed here (Implementation_Plans is not Tickets/). Keep `draft` while preparing the
Task batch; update it after the combined plan-and-Task review.

### Save gate

1. Write the file to disk.
2. Re-read the file and assert it exists and is non-empty.
3. Record `plan_path` on the run context.
4. Continue to Task drafting. Present the complete plan with the Task batch at the material
   publication review point; a path plus summary is insufficient.

**STOP before Task creation:** PHASE 3 must check `plan_path` exists. If missing → STOP with
"Implementation Plan not saved; refusing Task creation."

No separate `proceed` gate is needed between saving the local plan and drafting Tasks. Edits must
still cover every acceptance criterion before publication.
