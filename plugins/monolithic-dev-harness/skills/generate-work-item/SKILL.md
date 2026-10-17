---
name: generate-work-item
description: >
  Generates a raw Epic, Feature, User Story, or Task work item from a title and description: requirement bullets, acceptance criteria, Context7 research, a spec in the item's folder, and a Tickets/Ready draft; creates the item in the selected tracker after approval. Use when the user runs /generate-work-item, says "start ticket", "create a ticket", "create an issue", "create a user story", "create a feature", "create an epic", "generate a work item", or provides a work-item type plus a problem to turn into backlog work. For team-format enrichment (emoji sections, story-point drivers), use enrich-work-item instead. For plain-language requirement and acceptance-criteria prose, this skill delegates a sub-pass to generate-plain-language-documentation in PHASE 4.
license: MIT
---

# Generate Work Item

Conductor for turning a title + description into a **raw** spec, local draft, and (on approval)
provider work item. Load references as each phase needs them — this file is the score, not the
textbook.

## References

Start at `../../common/workflows/generate-work-item.md`:

- `../../common/workflows/generate-work-item.md` — type map, artifacts paths, Context7 protocol.
- `../../common/templates/output-formats.md` — **uniform ticket body**.
- `../../common/templates/` — **read-only shape contracts**. Validate every draft
  against the matching template before presenting.
- `../../common/specs/generate-work-item/` — spec forms, written where `../../references/document-layout.md` says:
  - `spec-epic.md`, `spec-feature.md`, `spec-work-item.md`
- `../../references/decomposition-rules.md` — hierarchy and parent rules.
- `../../references/ticket-structure.md` — draft file constraints (frontmatter, filename).
- `../../common/providers.md` — neutral artifact contract and provider translations.
- `../generate-plain-language-documentation/references/integration-notes.md` — prose polish sub-pass
  (PHASE 4).

Context7: read `context7-mcp` skill; server `plugin-context7-plugin-context7`.

**Not in scope:** enricher templates, emoji section layouts, or story-point driver tables — use the
`enrich-work-item` skill after drafting if the host team requires that format.

## Active tracker

Call `tracker_describe` before choosing a hierarchy, destination, provider call, or id format, and
follow [the tracker contract](../../references/tracker-contract.md).

---

## PHASE 0 — COLLECT INPUTS

Gather inputs **one at a time** via the host UI. Each step: brief purpose, required vs optional.

| Input | Required | Purpose |
| --- | --- | --- |
| `title` | yes | Short work-item title |
| `description` | yes | Problem statement or scope in the author's words |
| `work_item_type` | yes | `epic` \| `feature` \| `user-story` \| `task` |
| `parent` | only for a Task | Parent id or tracker link (Epic→Feature, Feature→Story, Story→Task) |
| `attachment` | no | Supporting doc URL or artifacts path |
| `language` | no | `en` \| `pt-br`, default **pt-BR**. When omitted, follow the existing Locale rule (match
  `description`'s language) instead of forcing the default. |

Also accept flags from `/generate-work-item` or conversational inference (see Examples).

Normalize the Agile type and immediate parent:

| Input | Work item type | Parent | Parent type when given |
| --- | --- | --- | --- |
| `epic` | Epic | none | — |
| `feature` | Feature | optional | Epic |
| `user-story` | User Story | optional | Feature |
| `task` | Task | required | User Story |

A Feature or a User Story may stand alone. Do not ask for a parent the user did not give, and do
not invent one. Only a Task needs a parent: if it is missing, STOP and ask once. If a given parent
has the wrong type: STOP and report (see `decomposition-rules.md`).

Ask `harness document path` for every document's path; it reads `artifacts_path` from
`.harness/settings.json` and places the document in its work item's folder
(`../../references/document-layout.md`).

---

## PHASE 1 — INGEST

1. Record normalized inputs.
2. If `parent` is provided, read it through the selected provider connector. Capture title,
   description, type, and chain. Verify parent type matches the common hierarchy.
3. If `attachment` is a path: read it. If URL: fetch or summarize. Note failures in spec References.
4. If the source is a `product-spec` folder or `SPEC.md`, read the kernel and every path in
   `companions:`. Capture the relevant `CAP-N` values and treat their intent, success conditions,
   constraints, non-goals, UX contracts, and `AD-N` rules as authoritative. Do not silently broaden
   or reinterpret them.

---

## PHASE 2 — RESEARCH (Context7)

**Always run before drafting.** Read `context7-mcp` skill, then:

1. Extract tech-stack tokens from `title`, `description`, `attachment`, and parent body.
2. Up to **3 libraries**: `resolve-library-id` → pick best match → `query-docs`.
3. If Context7 unavailable: proceed with `source: [manual]` and supplied refs only.

Output: research bundle for the spec blueprint.

Research may clarify current implementation facts, but it cannot overwrite a supplied product
contract. A contradiction becomes an explicit question back to `product-spec` or its owning
companion skill.

---

## PHASE 3 — WRITE SPEC

Pick blueprint from `../../common/specs/generate-work-item/`:

| `work_item_type` | Blueprint |
| --- | --- |
| `epic` | `spec-epic.md` |
| `feature` | `spec-feature.md` |
| `user-story` | `spec-work-item.md` |
| `task` | `spec-work-item.md` |

Write to the path `harness document path --type spec --new <type> --title "<title>" [--parent <key>]`
prints (`--item <key>` when the item exists; see `../../references/document-layout.md`). Populate
all sections from inputs + research.
**Do not skip** — spec is the analysis artifacts path.

When a product spec exists, this file is work-item analysis and traceability rather than a second
product contract: cite the source `SPEC.md`, list the `CAP-N` values covered, and record only the
work-item-specific interpretation and research. Never duplicate or renumber capabilities.

---

## PHASE 4 — GENERATE DRAFT

**Read `../../common/templates/output-formats.md` and the matching canonical contract
first.** Every draft uses the **same** body shape (canonical templates are immutable — conform, do
not modify):

- `# <Title>`
- `[[<spec file name without .md>]]` wikilink under the title (the spec's final name)
- `## Requisitos` — requirement bullets (from `description`, parent context, attachment, research)
- `## Critérios de Aceite` — `- [ ]` checkboxes, testable, infinitive verbs

Path: `harness document path --type ticket --new <type> --title "<title>" [--parent <key>]`, in
`Tickets/Ready/` only — never the artifacts path.

**Plain-language sub-pass:** Before presenting, read
`../generate-plain-language-documentation/references/integration-notes.md` § generate-work-item and
run a `work-item-prose` pass on `## Requisitos` and `## Critérios de Aceite` (glossary verification
when locale is pt-BR).

Frontmatter uses `provider`, string `provider_id`, and string `parent_id` per `ticket-structure.md`.
Never emit legacy provider-specific identity fields.

Present title, requirements, acceptance criteria, spec path, and draft path in chat.

---

## PHASE 5 — GATE & DESTINATION

**── GATE —** Before any tracker write, ask the `publish-items` approval gate with the drafts as `--artifact`s (see the harness skill's approval protocol).
Silence is not approval.

Then ask **where to persist** (if the user has not already chosen):

1. **The selected tracker** — create the item and its parent relation through the gateway.
2. **Chat only** — formatted markdown ready to copy.

If the user named no destination and wants chat-only output, write nothing unless they approve it.

---

## PHASE 6 — CREATE (selected provider)

Translate through `../../common/providers.md`: `tracker_create_work_item` with the harness kind and
`parentRef`; the tracker's adapter maps the kind, the parent relation and any labels.

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
- **Hierarchy invariants** — a parent is optional except for a Task; never link Story to Epic;
  always pass `type: "parent"` on link.
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
