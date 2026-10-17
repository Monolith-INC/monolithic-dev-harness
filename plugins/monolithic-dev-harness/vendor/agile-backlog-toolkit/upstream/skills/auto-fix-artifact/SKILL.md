---
name: auto-fix-artifact
description: >
  Validates an agile artifact (Epic, Feature, or User Story) and automatically fixes any issues found. Accepts an Azure workitem ID, artifacts path document, filesystem reference, or pasted string. If validation passes, outputs the report. If validation fails, it shows the report, asks for permission to fix, systematically corrects each problem based on the quality gate rules, and offers to save the corrected version back to Azure or the artifacts path.
license: MIT
---

# auto-fix-artifact

Validates a single agile artifact and offers an auto-fix workflow if issues are found. It uses the `validate-artifact` quality gates and applies fixes based on the same reference rules.

References (shared, in `../../references/`):
- `decomposition-rules.md` — hierarchy, DoR, sizing, story-point heuristic.
- `ticket-structure.md` — body sections, frontmatter constraints, content hygiene.
- `azure-mechanics.md` — MCP calls, linking mechanics, rendering rules.
- `audit-checklist.md` — fidelity, coverage, DoR check definitions.

References (from `validate-artifact` skill, in `../validate-artifact/references/`):
- `validation-checks.md` — full check catalog per artifact type + category.
- `report-format.md` — terminal output template + report template.
- `canonical/canonical-validation-report.md` — **read-only shape contract** for validation reports
  (shared with `validate-artifact`). Do not edit; conform output to this template.

---

## PHASE 1 — INGEST AND VALIDATE

**Input:** Azure work item ID, artifacts path document path, filesystem reference, or pasted string.

1. **Ingest:** 
   - Parse the input to determine its source (local file, azure, or raw text).
   - If Azure ID: fetch via `wit_get_work_item(id=<id>, expand=relations)`.
   - If file path: read the markdown file.
   - If pasted string: parse as raw text.
2. **Validate:** Run the orchestrator critic (do not self-judge):

```bash
bin/agile-backlog-toolkit evaluate --skill auto-fix-artifact --file <path>
# or MCP tool: agile-backlog-toolkit-orchestrator → auto-fix-artifact with draft_content
```

For reflection retries, resubmit revised `draft_content` via MCP or re-run `evaluate` after saving.
Circuit breaker trips after 3 attempts or identical critiques → `blocked_requires_review`.
Resume only after human types `IMPLEMENTATION APPROVED` (or `ORCHESTRATOR_INTERACTIVE=1` CLI).
3. **Report:** Display the validation report to the user on the screen.

---

## PHASE 2 — DECISION GATE

**If all checks PASS:**
- Inform the user that the artifact is fully compliant.
- Save the report to the artifacts path (following the `validate-artifact` Phase 4 persist logic).
- Stop execution.

**If any checks FAIL or WARN:**
- Show the report to the user.
- Ask the user (using `ask_question` or standard prompt): *"Validation found issues. Would you like me to automatically fix these problems?"*
- Wait for user confirmation.
- If the user declines, save the report to the artifacts path and stop.
- If the user approves, proceed to Phase 3.

---

## PHASE 3 — AUTO-FIX

Systematically address each FAIL and WARN result:

### a) STRUCTURAL Fixes
- **Frontmatter:** Add missing `type:` keys, remove invalid `status:` keys.
- **Filename:** Suggest/apply filename renames to match `^(\d+|tech-debt|bug|task|spike)-[a-z0-9-]+`.
- **Body Sections:** Add missing required sections (e.g., `Contexto`, `Critérios de Aceite`, `Tarefas Técnicas`, etc.) with placeholder or derived content. 

### b) HIERARCHY Fixes
- If parent is missing or wrong type, ask the user to provide a valid parent ID or search Azure DevOps to find a suitable parent feature/epic.
- Create parent links if the artifact is in Azure.

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
2. **Prompt for Save:** Ask the user: *"The artifact has been corrected. Would you like to save this version?"* with options depending on the source:
   - "Save to Azure DevOps" (if source was Azure, uses `wit_update_work_item`)
   - "Save to Artifacts/Artifacts" (if source was file/text, uses `write_to_file`/`replace_file_content`)
   - "Discard"
3. **Persist Report:** Save the final validation report with `bin/agile-backlog-toolkit validate --file <path> --persist`, which writes to `.agile-backlog-toolkit/reports/`.

---

## Guardrails
- **User Consent:** Never overwrite Azure work items or local files without explicit user approval in Phase 4.
- **Traceability:** When updating Azure, ensure a comment is added noting that the artifacts path applied automated quality fixes.
