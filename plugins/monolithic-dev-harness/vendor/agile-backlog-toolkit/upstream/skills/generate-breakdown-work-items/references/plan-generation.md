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
| `id` | `wit_get_work_item(id, expand=relations)` |
| `url` | Extract id via `../../references/azure-mechanics.md` (URL→id), then same as `id` |
| `path` | Read the markdown file; parse frontmatter + body |

Determine `work_item_type`:

- Azure: `System.WorkItemType` (`User Story` | `Feature` | `Epic` | …)
- Artifacts: frontmatter `work_item_type` / `type: feature` / Feature folder / ticket sections

**Branch:**

- **User Story** → continue ingest below, then PHASE 2.
- **Feature or Epic** → hand off to fan-out (`./fan-out.md`). Do **not** invent a plan for the parent itself.
- Anything else → STOP and report unsupported type.

### User Story ingest (required reads)

Always load **both** before drafting the plan:

1. **Parent Feature body**
   - Azure: follow `System.Parent` / parent relation; `wit_get_work_item` on the Feature id
   - Artifacts: `parent_id_artifacts path`, `parent_id`, or Features/ path from frontmatter / links
   - If parent Feature cannot be resolved: STOP and ask once for the Feature id or artifacts path
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
  destination: ...                           // from intake (unused until persist)
}
```

### Acceptance criteria extraction

Do **not** invent or rewrite ACs.

1. Prefer the Acceptance Criteria section:
   - en: `✅ Acceptance Criteria`
   - pt-BR: `✅ Critérios de Aceite`
2. Split on checkbox lines (`- [ ]` / `- [x]`) or numbered/bulleted items inside that section.
3. Azure: parse the same section from `System.Description` markdown.
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

Do not create Azure or artifacts path Task work items in this phase.

### Artifacts path and frontmatter

Resolve the artifacts root with `bin/agile-backlog-toolkit config --show`. If unset, ASK the user where
plans should go and save it with `config --set artifacts_path=<path>`. Never guess a location, and
never create a directory structure the user did not ask for.

**Filename:** `YYYY-MM-DD-<story-slug>.md`

- Date: run date (UTC or local host date, consistent within the run)
- `story-slug`: kebab-case from story title or id (`12345-intake-selection-ux`)
- If a file already exists for the same story today: append `-2`, `-3`, … — do not overwrite without asking

**Frontmatter:**

```yaml
---
type: implementation-plan
feature: <feature id or artifacts path>
story: <story id or artifacts path>
skill: generate-breakdown-work-items
language: en   # or pt-BR
destination: filesystem  # echo intake; informational
status: draft
created: YYYY-MM-DD
---
```

`status` is allowed here (Implementation_Plans is not Tickets/). Prefer `draft` until the user
accepts the plan; set `active` after confirmation if the host wants a gate.

### Save gate

1. Write the file to disk.
2. Re-read the file and assert it exists and is non-empty.
3. Record `plan_path` on the run context.
4. Present the path + a short summary to the user.

**STOP before Task creation:** PHASE 3 must check `plan_path` exists. If missing → STOP with
"Implementation Plan not saved; refusing Task creation."

### Optional confirmation

If the host UI supports it, show the plan summary and WAIT for accept/edit before PHASE 3.
Edits must still cover every AC; still no Task writes until the saved file reflects the accepted plan.
