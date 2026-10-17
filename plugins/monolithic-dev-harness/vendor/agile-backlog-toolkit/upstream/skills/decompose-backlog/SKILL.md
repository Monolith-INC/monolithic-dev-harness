---
name: decompose-backlog
description: >
  Decompose a parent work item into correctly-parented, audited child Stories. Use when the user asks to "break down this Feature", "decompose Epic/Feature N into stories", "create the user stories for <feature>", "groom this backlog item", or provides a Feature/Epic id and wants Stories drafted and created in Azure DevOps. Drives 7 phases: ingest the parent, split into right-sized Stories (1 Story = 1 sprint = 1 PR), draft them in the artifacts path, enrich to the team format, create them in Azure DevOps parented to the FEATURE, verify the hierarchy, and audit that every parent requirement has a home. Self-contained rules; two approval gates before any write. For plain-language scope lines and story narrative, delegates sub-passes to generate-plain-language-documentation in DRAFT and ENRICH phases.
license: MIT
---

# Decompose Backlog

Conductor for turning a parent work item into child Stories in Azure DevOps. Load the reference files
as each phase needs them — they carry the self-contained rules so this file stays a score, not a
textbook.

References (in `../../references/`):

- `decomposition-rules.md` — hierarchy, sizing (1 Story = 1 sprint = 1 PR), story-point heuristic, DoR.
- `ticket-structure.md` — draft format + draft file constraints (frontmatter, filename regex).
- `azure-mechanics.md` — create/link MCP calls + the two linking gotchas + rendering rules.
- `audit-checklist.md` — fidelity / coverage / DoR postflight.

References (skill-specific, in `./references/`):

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

Read the parent via `wit_get_work_item` (expand relations). Capture the original text VERBATIM, its
acceptance criteria, and the parent chain. Read any linked spike/wiki. Determine parent type.
**Branch:** if the parent is an **Epic**, STOP and ask whether to create intervening Feature(s) first
or target an existing child Feature (see decomposition-rules.md → Parent-type branch). Stories never
attach to an Epic.

### 2. DECOMPOSE

Apply the sizing rule and story-point heuristic from `decomposition-rules.md`. Produce an ordered list
of Story stubs (title + one-line scope + dependencies), each tracing to a verbatim slice of the parent.
**── GATE 1 —** present the split and WAIT for explicit approval before drafting anything.

### 3. DRAFT

Per approved stub, write a local draft per `ticket-structure.md` and the canonical template matching
the run's `language` (`../../common/templates/canonical-user-story.md` for pt-BR,
`canonical-user-story.en.md` for en) — hook-valid frontmatter (`type`, no `status`, `language:` set
to the chosen value), filename regex with the Feature-id prefix, the 7 body sections in canonical
order using that language's labels. Content hygiene applies.

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
**── GATE 2 —** show the final body and WAIT for thumbs-up before any Azure write.

### 5. CREATE

Per `../../common/providers.md`, create each item with Markdown and its Feature as the immediate
parent. Azure DevOps uses native work-item types; Linear uses the `agile:user-story` label.

### 6. VERIFY (structural)

Read each created item back; assert the immediate parent and the Epic→Feature→Story chain.
Reconcile frontmatter with the assigned id (rename file, set `provider` and `provider_id`). A failed
assertion STOPS the run.

### 7. AUDIT (content + coverage)

Run `audit-checklist.md`: retrieve each item FRESH from Azure; check fidelity, build the
parent-requirement → Story coverage map (flag orphans and scope creep), confirm DoR. Emit the coverage
report. Any gap STOPS and reports — no silent patching.

## Operating rules

- Two hard gates (after DECOMPOSE, after ENRICH). Never write to the artifacts path or Azure without the
  matching approval.
- Every Azure-mutating step is followed by a read-back assertion.
- If the host repo keeps a session artifacts path, write a checkpoint after CREATE and after AUDIT.
