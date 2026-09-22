---
name: validate-artifact
description: >
  Validate a single agile artifact (Epic, Feature, User Story, or Task) against the toolkit rule set. Use when the user asks to "validate this story/feature/epic", "check this ticket", "is this artifact ready?", or provides a local draft path or provider item and wants a quality report. Accepts a local draft, Azure DevOps work item, or Linear issue. Runs all checks non-blocking and emits a terminal report + persisted report. One artifact per invocation.
license: MIT
---

# validate-artifact

Quality gate for a single agile artifact. Load reference files as each phase needs them.

References (shared, in `../../references/`):
- `decomposition-rules.md` — hierarchy, DoR, sizing, story-point heuristic.
- `ticket-structure.md` — body sections, frontmatter constraints, content hygiene.
- `azure-mechanics.md` — MCP calls, linking mechanics, rendering rules.
- `audit-checklist.md` — fidelity, coverage, DoR check definitions.

References (skill-specific, in `./references/`):
- `validation-checks.md` — full check catalog per artifact type + category.
- `report-format.md` — terminal output template + report template.
- `../../common/contracts/validate-artifact/canonical-validation-report.md` — **read-only shape contract** for reports
  report bodies. Do not edit; reproduce this structure when emitting reports.

---

## PHASE 1 — INGEST

**Input:** one local draft path or one provider item identifier.

Determine source from the argument:

**If local draft (file path argument):**
1. Read the markdown file. Parse frontmatter: extract `work_item_type`, `parent_id`,
   `provider_id`, `story_points`. Parse body: identify sections by emoji + label headings.
2. Derive artifact type from `work_item_type` frontmatter value.

**If Azure ID (numeric argument):**
1. Call `wit_work_item[get](id=<id>, expand=Relations)`.
2. Extract: `System.WorkItemType`, `System.Title`, `System.Description`,
   `Microsoft.VSTS.Scheduling.StoryPoints`, `System.Parent`.
3. Artifact type = `System.WorkItemType`.

Normalize into a unified artifact record:

```
{
  type:         "Epic" | "Feature" | "User Story" | "Task"
  title:        string
  body:         string  (full description / body text)
  story_points: number | null
  parent_id:    string | null
  source:       "artifacts path" | "azure-devops" | "linear"
  filename:     string | null   (artifacts path only — basename without path)
  provider:      "local" | "azure-devops" | "linear"
  provider_id:   string | null
  raw:          original parsed content
}
```

If artifact type cannot be determined: STOP and report —
`"Cannot detect artifact type — check work_item_type frontmatter (artifacts path) or System.WorkItemType (Azure)."`

If given multiple IDs or paths: process only the first and warn —
`"validate-artifact processes one artifact per invocation."`

---

## PHASE 2 — VALIDATE

**Prefer the deterministic orchestrator** (rule-based critic — no LLM self-judgment):

```bash
bin/agile-backlog-toolkit validate --file <path> [--persist]
# or quality-gate with mailbox error log:
bin/agile-backlog-toolkit evaluate --skill validate-artifact --file <path>
```

The Python critic implements every check in `./references/validation-checks.md`. On failure,
`evaluate` writes `.agentic/workflow_prompts/validate-artifact.error.log` for `correcao` resume.

Read `./references/validation-checks.md` for the complete check definitions, conditions, and
FAIL/WARN thresholds before running checks manually.

Run all four categories in order. Each check emits `{ name, result, detail }`.
No check halts sibling or subsequent checks on failure. Collect all findings.

### a) STRUCTURAL

**Local draft only:**
- `frontmatter-type-present` — FAIL if `type:` key absent from frontmatter.
- `frontmatter-status-absent` — FAIL if `status:` key present in frontmatter.
- `filename-regex` — FAIL if filename does not match `^(\d+|draft|tech-debt|bug|task|spike)-[a-z0-9-]+`.
  If source is Azure (no filename): emit SKIP.

**All sources:**
- If User Story: check each of the 7 required sections present in body.
  Emit `body-section-missing: <section name>` FAIL for each absent section.
- If Feature or Epic: check title non-empty AND description non-empty. FAIL if either absent.

### b) HIERARCHY

A Feature or a User Story with no parent is valid: its parent check passes with `no parent`. Pass
`hierarchy_parent_is_feature: false` only when the Story **has** a parent and it is not a Feature.

**User Story:**
1. If `parent_id` is set: `wit_work_item[get](id=artifact.parent_id)`. Assert
   `System.WorkItemType == "Feature"`.
2. Check `hierarchy-story-parent-is-feature` — FAIL if the parent is not a Feature (for example an
   Epic). PASS when there is no parent.

**Feature:**
1. If `parent_id` is set: `wit_work_item[get](id=artifact.parent_id)`. Assert
   `System.WorkItemType == "Epic"`.
2. Check `hierarchy-feature-parent-is-epic` — FAIL if the parent is not an Epic. PASS when there is
   no parent.

**Epic:**
1. Fetch children via `search_workitem` or relations from the ingested item.
   Assert no child has `System.WorkItemType == "User Story"`.
2. Check `hierarchy-epic-no-direct-stories` — FAIL if direct Story children found.

**Task:** assert its immediate parent is a User Story. A Task is the only type that must have a
parent.

If an MCP call fails (network / permission): emit `SKIP <check> — MCP unavailable: <error>` and
continue. Do not abort the run.

### c) CONTENT

**User Story only:**
- `content-complexidade-breakdown` — scan `📊 Complexidade` section for driver keywords
  (Escopo, Incerteza, Integrações, Dados, QA, Rollout). FAIL if absent.
- `content-story-points-set` — assert `story_points > 0`. FAIL if unset or 0.
- `content-descricao-original-present` — assert `📄 Descrição Original` section non-empty.
  FAIL if empty.

**All artifact types:**
- `content-no-machine-paths` — scan body for `/home/`, `/Users/`, `C:\`, `D:\`.
  WARN if found; include the matched path in detail.
- `content-no-meta-prose` — scan body for `TBD`, `to be defined`, `a definir` outside
  `@TODO` annotation context. WARN if found.

### d) DoR (Definition of Ready)

- `dor-title-clear` — assert title non-empty and word count > 5. FAIL if not met.
- `dor-description-present` — assert body / description non-empty. FAIL if not met.
- `dor-story-points-set` *(User Story only)* — assert `story_points > 0`. FAIL if not met.

---

## PHASE 3 — REPORT

Read `./references/report-format.md` for the exact output template before printing.

Print to terminal:
1. Header: `Validating <type> — "<title>" [<source>]`
2. Separator: 60 `=` characters.
3. Findings grouped by category (STRUCTURAL / HIERARCHY / CONTENT / DoR).
   Each line: `  [PASS|FAIL|WARN|SKIP]  <check-name>  —  <detail>`
4. Separator: 60 `-` characters.
5. Summary: `Summary: X passed · Y failed · Z warnings`
6. Outcome: `Outcome: PASS` (zero FAILs) or `Outcome: FAIL` (≥1 FAIL)

---

## PHASE 4 — PERSIST

Read `./references/report-format.md` for the report frontmatter template.

Path: `.agile-backlog-toolkit/reports/` (plugin-owned; written by `--persist`)

Filename: `<YYYY-MM-DD>-validate-<id-or-slug>.md`
- Use `provider_id` if available.
- Otherwise: derive slug from filename (strip extension) or from title (lowercase, spaces → hyphens, max 40 chars).

Frontmatter:
```yaml
---
date: <YYYY-MM-DD>
type: report
artifact: <azure-id or artifacts path-filename>
artifact_type: <Epic|Feature|User Story|Task>
source: <artifacts path|azure-devops|linear>
outcome: <pass|fail>
---
```

Body: reproduce the full terminal output from Phase 3 verbatim inside a fenced code block.

Do NOT include `status:` in frontmatter.

---

## Guardrails

- **No mutations.** This skill reads and reports only. Never write, update, or link work items.
- **Non-blocking.** Every check runs regardless of prior failures in the same category.
- **SKIP over ERROR.** If a provider connector fails, log SKIP with reason and continue.
- **One artifact per run.** Process only the first argument if multiple are given.
