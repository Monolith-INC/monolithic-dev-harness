---
name: decompose-backlog
description: >
  Decompose a parent work item into correctly-parented, audited children. A Feature parent yields Stories; an Epic parent yields Features and, under each, Stories — in one linear run. Use when the user asks to "break down this Feature/Epic", "decompose Epic/Feature N", "create the features and user stories for <epic>", "groom this backlog item", or provides a Feature/Epic id and wants the tree drafted and created in Azure DevOps. Drives 7 phases: ingest the parent, split into right-sized Features (Epic only) and Stories (1 Story = 1 sprint = 1 PR), draft them in the artifacts path, enrich to the team format, create them top-down in Azure DevOps (Features under the Epic, Stories under their FEATURE), verify the hierarchy, and audit that every parent requirement has a home. Self-contained rules; two approval gates before any write. For plain-language scope lines and story narrative, delegates sub-passes to generate-plain-language-documentation in DRAFT and ENRICH phases.
license: MIT
---

# Decompose Backlog

Conductor for turning a parent work item into its child tree in Azure DevOps: Feature → Stories
(*story mode*), or Epic → Features → Stories (*tree mode*). Load the reference files
as each phase needs them — they carry the self-contained rules so this file stays a score, not a
textbook.

References (in `../../references/`):

- `decomposition-rules.md` — hierarchy, Feature sizing (Epic → Feature), Story sizing (1 Story = 1 sprint = 1 PR), story-point heuristic, DoR, parent-type branch.
- `ticket-structure.md` — draft format + draft file constraints (frontmatter, filename regex).
- `azure-mechanics.md` — create/link MCP calls + the two linking gotchas + rendering rules.
- `audit-checklist.md` — fidelity / coverage / DoR postflight.

Shape contracts and sub-pass notes:

- `../../common/templates/canonical-feature.md` — **read-only shape contract** for Feature drafts in
  tree mode (Objetivo, Escopo, Critérios de Sucesso, Áreas/Módulos, Descrição Original).
- `../../common/templates/canonical-user-story.md` — **read-only shape contract** for enriched Story drafts (seven
  emoji sections per `ticket-structure.md`, pt-BR labels). Do not edit; validate every draft against
  this template when `language` is `pt-BR`.
- `../../common/contracts/decompose-backlog/canonical-user-story.en.md` — same shape contract with English section labels. Use when
  `language` is `en`.
- `../generate-plain-language-documentation/references/integration-notes.md` — prose polish sub-pass
  in DRAFT and ENRICH phases.

## Input

A parent work item **id** (Epic or Feature). Optional: target iteration, story-point ceiling override,
`language` (`en` | `pt-BR`, default **pt-BR**) — selects which canonical template and section-label
set (`ticket-structure.md` → Body sections) every drafted Story uses; set it once for the whole run
and record it as `language:` in each draft's frontmatter so `validate-artifact` checks against the
matching labels.

## Phases

### 1. INGEST

Read the parent via `tracker_get_work_item(ref=<id>)` through `workflow-integrations`. Capture the original text VERBATIM, its
acceptance criteria, and the parent chain. Read any linked spike/wiki. Determine parent type and the
mode (decomposition-rules.md → Parent-type branch):

- **Feature** → *story mode*. Continue to DECOMPOSE.
- **Epic** → *tree mode*. Also read the Epic's existing child Features (`tracker_list_children` and inspect each returned child): their titles, descriptions, and existing Stories. Continue to DECOMPOSE
  without asking; the tree proposal at GATE 1 is where the user steers.

Stories never attach to an Epic, in either mode.

If the parent references a `product-spec`, read `SPEC.md` and all `companions:` before decomposing.
Treat `CAP-N` intent and success conditions, product constraints, non-goals, UX contracts, and
`AD-N` rules as binding. Existing work-item prose does not override them silently.

### 2. DECOMPOSE

Apply the sizing rules and story-point heuristic from `decomposition-rules.md`.

- *Story mode:* an ordered list of Story stubs (title + one-line scope + dependencies + provisional
  points), each tracing to a verbatim slice of the Feature and the `CAP-N` values it covers.
- *Tree mode:* first the Features (Feature sizing rule): for each, title + one-line objective + the
  verbatim Epic slice it covers + `existing #<id>` or `new`. Then, under each Feature, its Story stubs
  as in story mode, each tracing to a slice of that Feature's slice. Every Epic slice must land in
  exactly one Feature.

Every relevant capability must land in at least one Story, and every Story must cite at least one
capability when a product spec exists. A new constraint or architectural choice discovered while
slicing goes back to the owning planning artifact; do not bury it in a Story.

**── GATE 1 —** present the whole split (the tree, in tree mode) as one outline and WAIT for explicit
approval before drafting anything. Edits the user asks for re-run DECOMPOSE; do not draft a partial
tree.

### 3. DRAFT

*Tree mode first:* per approved **new** Feature, write a local draft against
`../../common/templates/canonical-feature.md` — frontmatter `work_item_type: Feature`,
`parent_id: "<epic id>"`, filename `<epicId>-f<n>-<slug>.md`, Descrição Original = its verbatim Epic
slice. Existing Features get no draft; their Stories use the existing Feature id.

Per approved Story stub, write a local draft per `ticket-structure.md` and the canonical template matching
the run's `language` (`../../common/templates/canonical-user-story.md` for pt-BR,
`canonical-user-story.en.md` for en) — hook-valid frontmatter (`type`, no `status`, `language:` set
to the chosen value), filename regex with the Feature-id prefix, the 7 body sections in canonical
order using that language's labels, and `story_points:` set from the heuristic. Content hygiene
applies. In tree mode, a Story under a **new** Feature has no Feature id yet: name it
`<epicId>-f<n>-us<m>-<slug>.md` and set `parent_id: "pending:<epicId>-f<n>"` (the Feature draft's
filename stem). CREATE replaces the placeholder with the real id.

**Plain-language sub-pass:** Read
`../generate-plain-language-documentation/references/integration-notes.md` § decompose-backlog; run a
`generate-plain-language-documentation` pass on scope lines and section prose (glossary-verify via
`../generate-plain-language-documentation/references/assets/tech-glossary-en-pt-br.json` when locale
is pt-BR).

### 4. ENRICH

Tighten each draft to the team format: WHAT not HOW, ASCII diagrams, de-dup (each fact once),
story-point justification with the per-driver MAX. The enriched body IS the exact Azure description.

**Plain-language sub-pass:** Read
`../generate-plain-language-documentation/references/integration-notes.md` § decompose-backlog; polish
narrative paragraphs inside sections (not emoji headings; not story-point driver tables).
Glossary-verify via `../generate-plain-language-documentation/references/assets/tech-glossary-en-pt-br.json`
when locale is pt-BR.
**── GATE 2 —** show the final bodies (in tree mode: each Feature followed by its Stories, with
points) and WAIT for thumbs-up before any Azure write. One approval covers the whole batch; say so
when you ask.

### 5. CREATE

Per `../../common/providers.md` and `../../references/azure-mechanics.md`, create **top-down**:

1. *Tree mode:* each new Feature (`workItemType: "Feature"`, Markdown description), linked to the
   Epic with `type: "parent"`. Read it back, then rewrite every `parent_id: "pending:<stem>"` that
   points at it to the real id and rename the Feature draft with its id.
2. Each Story with Markdown, its points field set from `story_points`, and its **Feature** as the
   immediate parent.

Azure DevOps uses native work-item types; Linear uses the `agile:user-story` label. If a Feature
create fails, stop before creating any Story under it.

### 6. VERIFY (structural)

Read each created item back; assert the immediate parent, the Epic→Feature→Story chain, and (for
Stories) that the points field holds the draft's `story_points`.
Reconcile frontmatter with the assigned id (rename file, set `provider` and `provider_id`). A failed
assertion STOPS the run.

### 7. AUDIT (content + coverage)

Run `audit-checklist.md`: retrieve each item FRESH from Azure; check fidelity, build the
parent-requirement → Story coverage map (in tree mode, Epic slice → Feature → Story; flag orphans
and scope creep at both levels), confirm DoR. Emit the coverage
report. Any gap STOPS and reports — no silent patching.

## Operating rules

- Two hard gates (after DECOMPOSE, after ENRICH), in both modes. Never write to the artifacts path or
  Azure without the matching approval. The harness approval hook enforces GATE 2 for Azure writes.
- Tree mode is one run: no stop between the Feature level and the Story level.
- Every Azure-mutating step is followed by a read-back assertion.
- If the host repo keeps a session artifacts path, write a checkpoint after CREATE and after AUDIT.
