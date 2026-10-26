---
name: split-story
description: >
  Lateral story-sizing skill. Takes a single User Story and determines if it should be split, how many sub-stories to create, and what split pattern to use — then drafts sub-stories and hands them off. Use when the user asks "split this story", "is this story too big?", "analyze this story for sizing", or provides a artifacts path / Azure ID / file path / raw text and wants a split recommendation. One story per invocation.
license: MIT
---

# split-story

Lateral story-sizing skill. Load reference files as each phase needs them.

References (shared, in `../../references/`):
- `decomposition-rules.md` — 6-driver MAX heuristic, story-point ceiling, DoR, hierarchy rules.
- `ticket-structure.md` — body sections, frontmatter constraints, content hygiene.
- `azure-mechanics.md` — MCP calls, linking gotchas, rendering rules.

References (skill-specific, in `./references/`):
- `split-patterns.md` — split pattern catalog with detection signals and auto-selection rules.
- `scoring-guide.md` — 6-driver scoring table, ceiling logic, spike detection rule, discrepancy
  handling.
- `../../common/templates/canonical-user-story.md` — **read-only shape contract** for split sub-story drafts
  (seven emoji sections). Do not edit; validate output against this template.
- `../../common/contracts/split-story/canonical-spike.md` — **read-only shape contract** for spike stubs.
  Do not edit; validate spike output against this template.

---

## PHASE 1 — INGEST

**Input:** one of — local draft path, Azure work item ID, arbitrary file system path, or raw
text pasted inline.

Determine source from the argument:

**If local draft path** (path under the artifacts path, recognized by artifacts path prefix or `.md`
extension inside the artifacts tree):
1. Read the markdown file. Parse frontmatter: extract `work_item_type`, `story_points`,
   `parent_id`, `provider_id`. Parse body: identify sections by emoji + label headings.

**If Azure ID** (numeric argument):
1. Call `wit_get_work_item(id=<id>, expand=relations)`.
2. Extract: `System.Title`, `System.Description`,
   `Microsoft.VSTS.Scheduling.StoryPoints`, `System.Parent`.

**If file system path** (non-artifacts path to a `.md` or `.txt` file):
1. Read the file from disk. Parse as markdown. Extract any frontmatter if present; treat body
   as the full description.

**If raw text** (multi-line pasted content, no recognizable path or ID):
1. Use the pasted content directly as the body. No frontmatter to parse; treat the entire
   input as the story description.

Normalize into a unified artifact record:

```text
{
  title:                string | null   (frontmatter/title field, or first heading, or null)
  body:                 string          (full description / body text)
  story_points:         number | null   (null if not declared in any source)
  acceptance_criteria:  string[]        (each AC line from the ✅ Critérios de Aceite section;
                                         empty array if the section is absent)
  parent_id:             string | null
  provider:              "local" | "azure-devops" | "linear"
  provider_id:           string | null
  source:                "artifacts path" | "azure-devops" | "linear" | "filesystem" | "raw"
}
```

Extract `acceptance_criteria` by reading the `✅ Critérios de Aceite` section and splitting on
checkbox lines (`- [ ]` or `- [x]`). For Azure source, parse the same section from
`System.Description` markdown. For raw text or filesystem source, parse from the body if the
section heading is present; otherwise `acceptance_criteria = []`.

If artifact cannot be parsed (empty content, unreadable file, MCP error): STOP and report the
specific failure. Do not proceed.

---

## PHASE 2 — SCORE

Read `./references/scoring-guide.md` for the complete driver table, ceiling value, spike rule,
and discrepancy-handling protocol before scoring.

Apply the 6-driver MAX heuristic to the normalized artifact:

1. Score each driver (Escopo, Incerteza, Integrações, Dados, QA, Rollout) on the 1/2/3/5 scale.
2. `calculated_points = MAX(all driver scores)`.
3. Record which driver(s) are at the MAX — these are the dominant drivers.

**Discrepancy check** (run only if `story_points` is declared and non-null):
- If `declared == calculated`: proceed with `active_points = declared`.
- If `declared ≠ calculated`: follow the discrepancy-handling protocol in `scoring-guide.md`
  exactly — show both values with driver breakdown and wait for user choice.
  `active_points = user-chosen value`.

**If `story_points` not declared:** `active_points = calculated_points`. No prompt shown.

---

## PHASE 3 — ANALYZE

Read `./references/split-patterns.md` for the pattern catalog and auto-selection decision tree.

**Branch A — No split needed:**

If `active_points ≤ ceiling` (default 5, or override from invocation argument):

1. Print: `Story is right-sized at <active_points> pts (ceiling: <ceiling>).`
2. Print the driver breakdown (all six driver scores).
3. STOP. No files written. No further phases execute.

**Branch B — Spike recommended:**

If `Incerteza == 5` AND Incerteza is the sole MAX driver (no other driver also scored 5):

1. Present spike rationale: uncertainty dominates; scope-splitting does not reduce risk —
   investigation does.
2. Show the user the specific unknown that caused Incerteza=5 (derived from the story body).
3. Ask: "Recommend a Spike instead of a scope split. Shall I draft a Spike stub?"
4. Wait for user confirmation before proceeding to DRAFT.
   - Confirmed → proceed to DRAFT (Spike mode).
   - Declined → STOP.

**Branch C — Split:**

1. `split_count = ⌈active_points / ceiling⌉`.
2. Auto-select split pattern using the decision tree in `split-patterns.md`.
3. Show reasoning: one sentence per pattern considered; one winner with justification.
4. Derive `split_count` sub-story titles and one-line scopes.
5. Estimate point value per sub-story: re-apply driver scoring to the narrowed scope.
   Each sub-story should score ≤ ceiling after the split.
6. Map which ACs from the original story belong to each sub-story.

**── GATE 1: present split plan to user ──**

Show:
- Pattern chosen and why (one sentence)
- Number of sub-stories
- For each sub-story: proposed title + one-line scope + estimated points
- Which original ACs map to each sub-story

Wait for explicit approval (`yes` / `proceed` / `ok` or equivalent) before entering DRAFT.
If the user revises the plan (different pattern, different count, adjusted titles): incorporate
revisions and re-show the updated plan. Do not proceed until the plan is approved.

---

## PHASE 4 — DRAFT

Read `../../references/ticket-structure.md` and `../../references/decomposition-rules.md`
before writing any files.

**Spike mode** (Branch B confirmed):

1. Draft one local file at:
   `<artifacts>/Tickets/Ready/<parent_id>-spike-<slug>.md`
2. Fill all 7 body sections using the Spike stub format from `./references/scoring-guide.md`.
3. Fill each `[placeholder]` with content derived from the original story.

**Split mode** (Branch C approved):

For each approved sub-story:

1. Filename: `<parent_id>-<n>-<kebab-slug>.md` — e.g., `6868-1-register-flow.md`.
2. Path: `<artifacts>/Tickets/Ready/<filename>`.
3. Frontmatter (hook-valid — no `status:` and no `provider_id` before provider creation):

```yaml
---
date: <YYYY-MM-DD>
type: ticket
work_item_type: User Story
parent_id: <parent_id>
provider: local
story_points: <estimated-points>
---
```

4. Body: all 7 sections per `ticket-structure.md` and `./references/canonical/canonical-user-story.md`
   (in order):
   - 🎯 O quê
   - 💡 Por quê
   - 📋 Comportamento esperado
   - ✅ Critérios de Aceite
   - 🔧 Notas Técnicas
   - 📊 Complexidade — driver breakdown for this sub-story's narrowed scope
   - 📄 Descrição Original — the exact verbatim slice of the original story's ACs that this
     sub-story covers. No paraphrasing.

**Coverage check** (run after all files are written, before HANDOFF):

1. List every AC item from the original story.
2. For each item, confirm it appears in exactly one sub-story's `📄 Descrição Original`.
3. If any AC item appears in zero sub-stories: STOP and report
   `ORPHAN AC: <item>` — dropped requirement.
4. If any AC item appears in two or more sub-stories: STOP and report
   `DUPLICATE COVERAGE: <item>` — ambiguous scope.
5. Any gap or duplicate must be resolved by revising the draft files before HANDOFF.
   Do not silently patch — surface the issue to the user.

---

## PHASE 5 — HANDOFF

Present a summary:
- List each sub-story: title + point estimate + file path.
- Coverage confirmation: "All <N> original ACs covered."

Show options:

```text
Sub-stories drafted. What would you like to do?

1. Keep as local drafts — done; continue manually or via decompose-backlog.
2. Create in the configured provider and link to the parent Feature.
3. Discard drafts — delete files and stop.
```

Wait for user choice.

**Option 1 — Keep:**
Report file paths and stop. No further action.

**Option 2 — Provider:**
Read `../../common/providers.md` and use the selected Azure DevOps or Linear connector.

For each sub-story draft (in order):

1. `wit_create_work_item` with `Markdown description` = full body from the draft.
2. Assert response contains `System.Id`. If absent: STOP and report failure with the item
   title and the raw error.
3. `wit_work_items_link` with explicit `type: "parent"` linking the new item to
   `parent_id`.
4. Read back: `wit_get_work_item(id=<new_id>, expand=relations)`.
   Assert `System.Parent == parent_id`.
   Assert that the relations array contains no `System.LinkTypes.Related` links
   (no stray Related links from prior failed runs).
   If either assertion fails: STOP and report
   `LINK ASSERTION FAILED for <title>: expected parent <parent_id>, got <actual>`
   or `STRAY RELATED LINKS for <title>: <links found>`.
5. Update local draft frontmatter: set `provider_id: <new_id>`. Rename file to
   `<new_id>-<slug>.md`.

After all items: report each title, provider identifier, and parent link status.

**Option 3 — Discard:**
Delete each local draft file written in PHASE 4. Report `Drafts discarded.` and stop.

---

## Guardrails

- **One story per run.** Process only the first argument if multiple are given.
- **No silent patching.** Coverage gaps and duplicates surface to the user — never auto-resolved.
- **No provider writes without user consent.** Connector calls execute only if the user selects
  HANDOFF option 2.
- **Gate before draft.** DRAFT phase does not execute until GATE 1 is explicitly approved.
- **Spike ≠ split.** When Incerteza is the sole dominant driver, recommend a Spike; do not
  force a scope split.
