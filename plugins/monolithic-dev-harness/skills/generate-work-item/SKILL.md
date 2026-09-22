---
name: generate-work-item
description: >
  Generates a raw Epic, Feature, User Story, or Task work item from a title and description: requirement bullets, acceptance criteria, Context7 research, a Specs note, and a Tickets/Ready draft; creates the selected local, Azure DevOps, or Linear item after approval. Use when the user runs /generate-work-item, says "start ticket", "create a ticket", "create an issue", "create a user story", "create a feature", "create an epic", "generate a work item", or provides a work-item type plus a problem to turn into backlog work. For team-format enrichment (emoji sections, story-point drivers), use enrich-work-item instead. For plain-language requirement and acceptance-criteria prose, this skill delegates a sub-pass to generate-plain-language-documentation in PHASE 4.
license: MIT
---

# Generate Work Item

Conductor for turning a title + description into a **raw** spec, local draft, and (on approval)
provider work item. Load references as each phase needs them — this file is the score, not the
textbook.

References (start at `../../common/workflows/generate-work-item.md`):

- `../../common/workflows/generate-work-item.md` — type map, artifacts paths, Context7 protocol.
- `../../common/templates/output-formats.md` — **uniform ticket body**.
- `../../common/templates/` — **read-only shape contracts**. Validate every draft
  against the matching template before presenting.
- `../../common/specs/generate-work-item/` — spec forms written to `<artifacts>/Specs/`:
  - `spec-epic.md`, `spec-feature.md`, `spec-work-item.md`
- `../../references/decomposition-rules.md` — hierarchy and parent rules.
- `../../references/ticket-structure.md` — draft file constraints (frontmatter, filename).
- `../../common/providers.md` — neutral artifact contract and provider translations.
- `../generate-plain-language-documentation/references/integration-notes.md` — prose polish sub-pass
  (PHASE 4).

Context7: read `context7-mcp` skill; server `plugin-context7-plugin-context7`.

**Not in scope:** enricher templates, emoji section layouts, or story-point driver tables — use the
`enrich-work-item` skill after drafting if the host team requires that format.

---

## PHASE 0 — COLLECT INPUTS

Gather inputs **one at a time** via the host UI. Each step: brief purpose, required vs optional.

| Input | Required | Purpose |
| --- | --- | --- |
| `title` | yes | Short work-item title |
| `description` | yes | Problem statement or scope in the author's words |
| `work_item_type` | yes | `epic` \| `feature` \| `user-story` \| `task` |
| `parent` | when type ≠ epic | Parent id or Azure URL (Epic→Feature, Feature→Story) |
| `attachment` | no | Supporting doc URL or artifacts path |
| `language` | no | `en` \| `pt-br`, default **pt-BR**. When omitted, follow the existing Locale rule (match
  `description`'s language) instead of forcing the default. |

Also accept flags from `/generate-work-item` or conversational inference (see Examples).

Normalize the Agile type and immediate parent:

| Input | Work item type | Parent required |
| --- | --- | --- |
| `epic` | Epic | no |
| `feature` | Feature | Epic id |
| `user-story` | User Story | Feature id |
| `task` | Task | User Story id |

If `parent` is missing when required: STOP and ask once. If parent type mismatches hierarchy: STOP
and report (see `decomposition-rules.md`).

Resolve the artifacts path with `bin/agile-backlog-toolkit config --show`, which reads
`.agile-backlog-toolkit/config.json` and falls back to older locations. See
`../../references/project-config.md`.

---

## PHASE 1 — INGEST

1. Record normalized inputs.
2. If `parent` is provided, read it through the selected provider connector. Capture title,
   description, type, and chain. Verify parent type matches the common hierarchy.
3. If `attachment` is a path: read it. If URL: fetch or summarize. Note failures in spec References.

---

## PHASE 2 — RESEARCH (Context7)

**Always run before drafting.** Read `context7-mcp` skill, then:

1. Extract tech-stack tokens from `title`, `description`, `attachment`, and parent body.
2. Up to **3 libraries**: `resolve-library-id` → pick best match → `query-docs`.
3. If Context7 unavailable: proceed with `source: [manual]` and supplied refs only.

Output: research bundle for the spec blueprint.

---

## PHASE 3 — WRITE SPEC

Pick blueprint from `../../common/specs/generate-work-item/`:

| `work_item_type` | Blueprint |
| --- | --- |
| `epic` | `spec-epic.md` |
| `feature` | `spec-feature.md` |
| `user-story` | `spec-work-item.md` |
| `task` | `spec-work-item.md` |

Write to `<artifacts>/Specs/<prefix>-<kebab-slug>-spec.md`. Populate all sections from inputs + research.
**Do not skip** — spec is the analysis artifacts path.

---

## PHASE 4 — GENERATE DRAFT

**Read `../../common/templates/output-formats.md` and the matching canonical contract
first.** Every draft uses the **same** body shape (canonical templates are immutable — conform, do
not modify):

- `# <Title>`
- `[[Specs/<spec-basename>]]` wikilink under the title
- `## Requisitos` — requirement bullets (from `description`, parent context, attachment, research)
- `## Critérios de Aceite` — `- [ ]` checkboxes, testable, infinitive verbs

Path: `<artifacts>/Tickets/Ready/<prefix>-<kebab-slug>.md` only — never artifacts root or `Specs/`.

**Plain-language sub-pass:** Before presenting, read
`../generate-plain-language-documentation/references/integration-notes.md` § generate-work-item and
run a `work-item-prose` pass on `## Requisitos` and `## Critérios de Aceite` (glossary verification
when locale is pt-BR).

Frontmatter uses `provider`, string `provider_id`, and string `parent_id` per `ticket-structure.md`.
Never emit legacy provider-specific identity fields.

Present title, requirements, acceptance criteria, spec path, and draft path in chat.

---

## PHASE 5 — GATE & DESTINATION

**── GATE —** WAIT for explicit approval (`proceed`, `create it`, `go ahead`) before any write.
Silence is not approval.

Then ask **where to persist** (if the user has not already chosen):

1. **Azure DevOps** — create a native work item and parent relation.
2. **Linear** — create an issue with `parentId` and its managed `agile:*` type label.
3. **Local artifacts** — keep the neutral spec and draft only.
4. **Chat only** — formatted markdown ready to copy.

If the user named no destination and wants chat-only output, skip local/Azure unless they approve
artifacts path persistence.

---

## PHASE 6 — CREATE (selected provider)

Translate through `../../common/providers.md`. Azure uses native work item types and parent relations.
Linear uses issues, immediate `parentId`, and exactly one managed Agile type label. Local persistence
keeps the common frontmatter unchanged.

---

## PHASE 7 — VERIFY

When a remote provider was used:

1. Read the item back and assert its type, title, description, and immediate parent.
2. Update the local draft with `provider` and string `provider_id`.
3. Update spec frontmatter `ticket` with new id when applicable.

On assertion failure: STOP and report — do not claim success.

Append checkpoint to open `Agent_Sessions/` record when the host keeps a session artifacts path.

---

## Operating rules

- **Raw ticket only** — uniform `# Title` + `## Requisitos` + `## Critérios de Aceite`; no enricher
  sections in this skill.
- **Spec before ticket** — PHASE 3 always runs; Context7 feeds the spec.
- **Tickets/Ready only** for drafts.
- **One gate** before persistence writes.
- **Hierarchy invariants** — never link Story to Epic; always pass `type: "parent"` on link.
- **Hook-safe drafts** — valid frontmatter and filename per `ticket-structure.md`.
- **Locale** — an explicit `language` input wins; otherwise match the language of `description` for
  section labels and body prose. Default pt-BR when neither gives a signal.

## Examples

**Slash command:**

```
/generate-work-item --type user-story --parent 6869 --title "Login field validation" --description "Validate email and password with inline errors on the login form"
```

**Conversational trigger:**

> Start a feature ticket for OAuth2 login under epic 6800

→ Infer `work_item_type: feature`, `parent: 6800`, run full pipeline.

**Chat-only output:**

> Generate an epic for platform security — just show me the markdown

→ Run through PHASE 4, present body in chat; skip local/Azure unless user approves artifacts path save.
