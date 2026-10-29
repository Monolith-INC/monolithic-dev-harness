---
name: generate-work-item
description: >
  Generates a raw Epic, Feature, User Story, or Task work item from a title and description: requirement bullets, acceptance criteria, Context7 research, a Specs note, and a Tickets/Ready draft; creates the item in the selected tracker after approval. Use when the user runs /generate-work-item, says "start ticket", "create a ticket", "create an issue", "create a user story", "create a feature", "create an epic", "generate a work item", or provides a work-item type plus a problem to turn into backlog work. For team-format enrichment (emoji sections, story-point drivers), use enrich-work-item instead. For plain-language requirement and acceptance-criteria prose, this skill delegates a sub-pass to generate-plain-language-documentation in PHASE 4.
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
| `parent` | for a task | Parent id or tracker link (Epic→Feature, Feature→Story, Story→Task) |
| `attachment` | no | Supporting doc URL or artifacts path |
| `language` | no | `en` \| `pt-br`, default **pt-BR**. When omitted, follow the existing Locale rule (match
  `description`'s language) instead of forcing the default. |

Also accept flags from `/generate-work-item` or conversational inference (see Examples).

Normalize the Agile type and immediate parent:

| Input | Work item type | Parent |
| --- | --- | --- |
| `epic` | Epic | none |
| `feature` | Feature | optional; an Epic |
| `user-story` | User Story | optional; a Feature |
| `task` | Task | required; a User Story |

A Feature or Story may stand alone: do not invent a parent or ask for one the user did not name. If
a Task has no parent: STOP and ask once. If a parent's type mismatches the hierarchy: STOP and
report (see `decomposition-rules.md`).

Every tracker read and write goes through the harness gateway (`tracker_*` tools); never call a
tracker's own tools. Ask `harness document path` for the spec's and the draft's paths
(`../../references/document-layout.md`).

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

Write to the path `harness document path --type spec --new <type> --title "<title>"` prints
(`--item <key>` once the item exists). Populate all sections from inputs + research.
**Do not skip** — spec is the analysis artifacts path.

---

## PHASE 4 — GENERATE DRAFT

**Read `../../common/templates/output-formats.md` and the matching canonical contract
first.** Every draft uses the **same** body shape (canonical templates are immutable — conform, do
not modify):

- `# <Title>`
- `[[Specs/<spec-basename>]]` wikilink under the title
- `## Requisitos` (English: `## Requirements`) — requirement bullets (from `description`, parent
  context, attachment, research)
- `## Critérios de Aceite` (English: `## Acceptance Criteria`) — `- [ ]` checkboxes, testable,
  infinitive verbs

Use one locale's labels throughout; the validator reads both locales but refuses a mix.

Path: the one `harness document path --type ticket --new <type> --title "<title>"` prints, in
`Tickets/Ready/` at the project root — never the artifacts root.

**Plain-language sub-pass:** Before presenting, read
`../generate-plain-language-documentation/references/integration-notes.md` § generate-work-item and
run a `work-item-prose` pass on `## Requisitos` and `## Critérios de Aceite` (glossary verification
when locale is pt-BR).

Frontmatter uses `provider`, string `provider_id`, and string `parent_id` per `ticket-structure.md`.
Never emit legacy provider-specific identity fields.

Present title, requirements, acceptance criteria, spec path, and draft path in chat.

---

## PHASE 5 — GATE & DESTINATION

**── GATE —** Show the draft with `harness workflow show --artifact <draft>`, then ask
`harness decision present --gate publish-items` with the draft as `--artifact`. Silence is not
approval.

The destination is the selected tracker. Write nothing else unless the user asks for chat-only
output.

---

## PHASE 6 — CREATE (selected provider)

Create the item with `tracker_create_work_item` per `../../common/providers.md`: the harness kind,
`parentRef` the immediate parent, and the approved draft's body word for word. The tracker's
adapter maps kinds, parent relations and labels. With the local tracker, creating the item turns its
draft into the tracked ticket.

---

## PHASE 7 — VERIFY

After creation:

1. Read the item back with `tracker_get_work_item` and assert its type, title, description, and immediate parent.
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

→ Run through PHASE 4, present body in chat; write nothing unless the user approves it.
