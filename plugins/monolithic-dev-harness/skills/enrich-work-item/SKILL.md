---
name: enrich-work-item
description: >
  Enriches an existing Epic, Feature, User Story, or Task into the host team's structured format using type-specific enricher prompts (emoji sections, scope blocks, complexity drivers, ASCII diagrams). Use when the user runs /enrich-work-item, asks to "enrich a ticket", "enrich this issue", "format this user story", "polish this feature", "structure this epic", or provides a path, URL, or pasted text plus work-item type. For raw title + requirement bullets from scratch, use generate-work-item instead. For plain-language narrative inside enricher sections, this skill delegates a sub-pass to generate-plain-language-documentation after enricher assembly.
license: MIT
---

# Enrich Work Item

Conductor for applying the **enricher pattern** to an existing work-item description. Load references
as each phase needs them.

References (start at `../../common/workflows/enrich-work-item.md`):

- `../../common/workflows/enrich-work-item.md` — type map, enricher routing, artifacts paths.
- `../../common/templates/output-formats.md` — per-type output contracts.
- `../../common/templates/` — **read-only shape contracts**. Validate enriched
  output against the matching template before presenting.
- `../../common/workflows/enrichers/` — **authoritative** prose rules:
  - `epic-enricher.prompt.md`, `feature-enricher.prompt.md`, `work-item-enricher.prompt.md`
- `../../common/specs/enrich-work-item/` — spec forms for optional analysis artifacts.
- `./references/examples/` — illustrative dummy outputs (content reference only; shape contract is
  `../../common/templates/canonical-<type>.md`).
- `../../references/decomposition-rules.md` — hierarchy, story-point heuristic.
- `../../references/ticket-structure.md` — draft file constraints.
- `../../common/providers.md` — neutral artifact contract and provider translations.
- `../generate-plain-language-documentation/references/integration-notes.md` — prose polish sub-pass
  (PHASE 4).

**Not in scope:** generating a raw work item from a title alone — use `generate-work-item` first.

## Active tracker

Call `tracker_describe` before choosing a hierarchy, destination, provider call, or id format, and
follow [the tracker contract](../../references/tracker-contract.md).

---

## PHASE 0 — COLLECT INPUTS

Gather inputs **one at a time** via the host UI. Each step: brief purpose, required vs optional.

| Input | Required | Purpose |
| --- | --- | --- |
| `source` | yes | `url` \| local `path` \| pasted `text` — the material to enrich |
| `work_item_type` | yes | `epic` \| `feature` \| `user-story` \| `task` |
| `parent` | only for a Task | Parent id or tracker link for hierarchy context; Features and Stories may have none |
| `attachment` | no | Extra doc URL or path |

Accept `/enrich-work-item` flags or conversational inference (see Examples).

Normalize type → enricher + the tracker kind (`tracker_describe` `kinds`) per `pipeline.md`.

Ask `harness document path` for every document's path; it reads `artifacts_path` from
`.harness/settings.json` and places the document in its work item's folder
(`../../references/document-layout.md`).

---

## PHASE 1 — INGEST


1. Load `source`:
   - **Tracker link or id** — the id per `tracker_describe` `ids`, then `tracker_get_work_item(ref=<id>)`,
     enumerate `AttachedFile` relations, parse description for linked docs/URLs/paths, fetch attachment
     and referenced content into `supplementary_context`. Set **Descrição Original** from
     its `description` verbatim.
   - **path** — read local markdown; capture body verbatim.
   - **url** (not a tracker link) — fetch external doc; capture description verbatim.
   - **text** — treat pasted content as the description to enrich.
2. If `parent` provided: read it with `tracker_get_work_item(ref=<parent>)` through
   `workflow-integrations` and capture the parent chain for context and filename prefix.
   When `source` is a tracker item and `parent` omitted, use its `parent_id`.
3. If `attachment` provided: read or fetch; fold into enricher context (dedupe against tracker
   attachments already ingested).
4. Preserve **Descrição Original** text exactly for the enricher output section.

---

## PHASE 2 — ROUTE ENRICHER

Read the common output contract and matching enricher:

| `work_item_type` | Enricher |
| --- | --- |
| `epic` | `enrichers/epic-enricher.prompt.md` |
| `feature` | `enrichers/feature-enricher.prompt.md` |
| `user-story` | `enrichers/work-item-enricher.prompt.md` |
| `task` | `enrichers/task-enricher.prompt.md` |

Load enricher prompts from `../../common/workflows/enrichers/`.

Follow enricher **Contexto Obrigatório** when host monorepo docs exist; skip gracefully when absent.

For user-story sources, classify Bug vs User Story per enricher §1 keywords when applicable.

---

## PHASE 3 — WRITE SPEC (optional artifacts path)

When the user will persist locally, fill the matching common `spec-*.md`
into the path `harness document path --type spec --item <key>` prints (`--new` before the item
exists; see `../../references/document-layout.md`). Skip when destination is chat-only.

---

## PHASE 4 — ENRICH

Apply the enricher rules to produce the **exact** output format defined in enricher §4 (Epic/Feature) or
§6 (work item). The enriched body IS the deliverable — emoji sections, scope blocks, complexity
drivers, ASCII diagrams as the enricher specifies.

**Plain-language sub-pass:** Read
`../generate-plain-language-documentation/references/integration-notes.md` § enrich-work-item; polish
narrative paragraphs inside sections (not emoji headings; not **Descrição Original**). Glossary-verify
when locale is pt-BR.

Run the enricher **Checklist de Auto-Revisão** before presenting.

Compare shape against `../../common/templates/canonical-<type>.md` (read-only contract; do not
edit). Use `./references/examples/example-<type>.md` only for illustrative content patterns.

Present the enriched markdown in chat. Suggest a title outside the markdown block when the enricher
requires it (work-item enricher).

---

## PHASE 5 — GATE & DESTINATION

**── GATE —** Save the enriched body as a draft file, show it, then ask the `publish-items`
approval gate with the draft as `--artifact` (see the harness skill's approval protocol). Silence is
not approval. An existing item is changed with `tracker_update_work_item` (`description`, and
`title` when it changed), keeping the original text in its Original Description section; a new item
is created with `tracker_create_work_item`. Read the item back after the write.

Then ask **where to persist** (if not already chosen):

1. **The selected tracker** — create or update the item through the gateway.
2. **Chat only** — formatted markdown ready to copy.

If no destination was named and the user wants chat-only, write nothing unless they approve it.

---

## PHASE 6 — PERSIST

Translate the common contract through the selected provider per `../../common/providers.md`.
Artifacts use only `provider`, string `provider_id`, and string `parent_id`.

---

## PHASE 7 — VERIFY

When a remote provider was used, read back the parent and description. Update the draft's neutral
provider identity fields when creating new items.

On failure: STOP and report.

Append checkpoint to open `Agent_Sessions/` record when the host keeps a session artifacts path.

---

## Operating rules

- **Enricher is authoritative** — output matches enricher § output format, not generate-work-item's
  uniform three-part layout.
- **Verbatim original** — always include Descrição Original from ingest (work-item description only;
  attachment text feeds enrichment context, not Descrição Original).
- **WHAT not HOW** — per enricher quality rules.
- **One gate** before persistence writes.
- **Locale** — Português BR for host-team enrichers unless the source is clearly another language.

## Examples

**Slash command:**

```
/enrich-work-item --type feature --source Tickets/Ready/6800-oauth-login.md --parent 6800
```

**Conversational trigger:**

> Enrich this user story — [pasted description]

→ Infer `work_item_type: user-story`, `source: text`, run enricher pipeline.

**Tracker source:**

> Format issue 6871 in the team template

→ `source: url` (tracker link), read with `tracker_get_work_item` (work item + attachments + description refs),
enrich, present for approval.
