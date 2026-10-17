---
name: auto-fix-artifact
description: >
  Validates an agile artifact (Epic, Feature, or User Story) and automatically fixes any issues found. Accepts a tracker work-item id or link, artifacts path document, filesystem reference, or pasted string. If validation passes, outputs the report. If validation fails, it shows the report, asks for permission to fix, systematically corrects each problem based on the quality gate rules, and offers to save the corrected version back to the tracker or the artifacts path.
license: MIT
---

# auto-fix-artifact

Validates a single agile artifact and offers an auto-fix workflow if issues are found. It uses the `validate-artifact` quality gates and applies fixes based on the same reference rules.

References (shared, in `../../references/`):
- `decomposition-rules.md` — hierarchy, DoR, sizing, story-point heuristic.
- `ticket-structure.md` — body sections, frontmatter constraints, content hygiene.
- `audit-checklist.md` — fidelity, coverage, DoR check definitions.

References (from `validate-artifact` skill, in `../validate-artifact/references/`):
- `validation-checks.md` — full check catalog per artifact type + category.
- `report-format.md` — terminal output template + report template.
- `../../common/contracts/validate-artifact/canonical-validation-report.md`: **read-only shape
  contract** for validation reports (shared with `validate-artifact`). Do not edit; conform output to this template.

---

## PHASE 1 — INGEST AND VALIDATE

**Input:** tracker work-item id or link, artifacts path document path, filesystem reference, or pasted string.

1. **Ingest:** 
   - Parse the input to determine its source (local file, tracker item, or raw text).
   - If a tracker id or link: fetch it with `tracker_get_work_item(ref=<id>)`.
   - If file path: read the markdown file.
   - If pasted string: parse as raw text.
2. **Validate:** Run the orchestrator critic (do not self-judge):

```bash
bin/agile-backlog-toolkit evaluate --skill auto-fix-artifact --file <path>
# or MCP tool: agile-backlog-toolkit-orchestrator → auto-fix-artifact with draft_content
```

For reflection retries, resubmit revised `draft_content` via MCP or re-run `evaluate` after saving.
Circuit breaker trips after 3 attempts or identical critiques → `blocked_requires_review`.
Each call evaluates the supplied draft once and returns its findings. FAIL is a completed review, not a tool failure. The actor revises and resubmits the draft. If reflection stalls or exhausts its budget, review the findings and start a fresh draft-review cycle with `attempt=0`; pass returned `reflection.last_critiques` on continuing cycles. This does not authorize implementation, publication or saving. General implementation approval rules are unchanged.
3. **Report:** Display the validation report to the user on the screen.

---

## PHASE 2 — DECISION GATE

**If all checks PASS:**
- Inform the user that the artifact is fully compliant.
- Save the report to the artifacts path (following the `validate-artifact` Phase 4 persist logic).
- Stop execution.

**If any checks FAIL or WARN:**
- Show the report to the user.
- Ask the user through `harness decision present` (see the harness skill's human-decisions contract): *"Validation found issues. Would you like me to automatically fix these problems?"*
- Wait for user confirmation.
- If the user declines, save the report to the artifacts path and stop.
- If the user approves, proceed to Phase 3.

---

## PHASE 3 — AUTO-FIX

Systematically address each FAIL and WARN result:

### a) STRUCTURAL Fixes
- **Frontmatter:** Add missing `type:` keys, remove invalid `status:` keys.
- **Filename:** Suggest/apply filename renames to match `^(\d+|draft|tech-debt|bug|task|spike)-[a-z0-9-]+`.
- **Body Sections:** Add the missing sections of the item type's template (`../../common/templates/canonical-*.md`, in the draft's language) with content derived from the item, keeping its original text in Original Description.

### b) HIERARCHY Fixes
- A missing parent is not a defect for an Epic, Feature, or User Story; leave it alone. Only a Task needs a parent.
- If a parent has the wrong type (for example a Story under an Epic), or a Task has none, ask the user for a valid parent ID or find one with `tracker_search_work_items`.
- Create parent links in the tracker only for the parent the user confirms.

### c) CONTENT Fixes
- **Complexidade:** Add the `📊 Complexidade` section with default/inferred values for Escopo, Incerteza, etc.
- **Story Points:** If missing or 0, analyze the complexity and suggest a story point value based on `decomposition-rules.md`, then update it.
- **Descricao Original:** Add `📄 Descrição Original` if missing.
- **Hygiene:** Remove local machine paths and replace `TBD`/`to be defined` with proper `@TODO` annotations.

### d) DoR Fixes
- Expand title if too short.
- Generate a description body if absent.

---

## PHASE 4 — OUTPUT & PERSIST

1. **Review:** Output the corrected version of the artifact (or a diff) to the screen.
2. **Save with approval:** save the corrected version as a draft file and show it. Depending on the
   source:
   - A tracker item: ask the `publish-items` approval gate with the draft as `--artifact`, then
     write it with `tracker_update_work_item` (`description`, and `title` when it changed) and read
     it back.
   - A local file: ask the `approve-document` gate with the draft as `--artifact`, then save it.
   - Otherwise discard it.
3. **Persist Report:** Save the final validation report with `bin/agile-backlog-toolkit validate --file <path> --persist`, which writes to `.harness/backlog/reports/`.

---

## Guardrails
- **User Consent:** Never overwrite a tracker item or a local file without its approval in Phase 4.
- **Traceability:** When updating a tracker item, ensure a comment is added noting that the artifacts path applied automated quality fixes.
