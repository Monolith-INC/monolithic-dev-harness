---
name: generate-plain-language-documentation
description: >
  Writes and rewrites human-facing prose in plain language — documentation, reports, guides, proposals, README sections, work-item descriptions, acceptance-criteria narratives, and any non-code text. Use when the user mentions documentation, documenting, writing prose, explaining something in plain language, making text readable, translating technical content for humans, or any action involving written text other than code — even if they do not say "documentation." Also invoke when sibling skills (generate-work-item, enrich-work-item, decompose-backlog) need polished requirement bullets or narrative sections. Not for dense agent-facing prompts, cheat sheets, or SKILL.md bodies — those may stay compressed.
license: MIT
---

# Generate Plain-Language Documentation

Conductor for turning technical source material into prose a feature owner, tech lead, or developer
can read once without cross-referencing. Load references as each phase needs them — this file is the
score, not the textbook.

References (start at `./references/pipeline.md`):

- `./references/pipeline.md` — phase map, artifacts paths, sibling-skill hooks.
- `./references/plain-language-principles.md` — hard rules, default structure, quality gate.
- `./references/glossary-usage.md` — **required** when `language` is `pt-br` or when verifying
  technical terms in any locale.
- `./references/output-formats.md` — deliverable shapes by `document_type`.
- `./references/integration-notes.md` — how `generate-work-item`, `enrich-work-item`, and
  `decompose-backlog` delegate prose passes to this skill.

Glossary path: `./references/assets/tech-glossary-en-pt-br.json` (bundled with the skill).

Resolve the artifacts path with `bin/agile-backlog-toolkit config --show` when persisting output. If it is
unset, ask the user where to write — never assume a location. Not needed for loading skill assets.

**Not in scope:** creating Azure work items, enricher emoji layouts, or backlog hierarchy — use the
sibling skills for those; call this skill for the **prose** inside their outputs.

---

## PHASE 0 — COLLECT INPUTS

Gather inputs **one at a time** via the host UI. Each step: brief purpose, required vs optional.

| Input | Required | Purpose |
| --- | --- | --- |
| `source` | yes | `text` \| local `path` \| `url` — material to rewrite or expand |
| `audience` | no | Least technical reader; default: feature owner unfamiliar with the stack |
| `language` | no | `en` (default) \| `pt-br` — drives glossary pass |
| `document_type` | no | `general` \| `report` \| `guide` \| `work-item-prose` — picks output contract |

Accept `/generate-plain-language-documentation` flags or conversational inference (see Examples).

---

## PHASE 1 — INGEST & COMPLETENESS CONTRACT

1. Load `source`:
   - **path** — read local markdown; capture body.
   - **url** — fetch external doc; capture content.
   - **text** — treat pasted content as the source.
2. Read `./references/plain-language-principles.md` § Completeness contract.
3. Inventory every decision, problem, evidence item, and open question that must survive in the output.
   This list is the completeness contract — do not drop items during drafting.

---

## PHASE 2 — DRAFT

Read `./references/plain-language-principles.md` and `./references/output-formats.md` for the chosen
`document_type`.

1. Identify the least technical reader in `audience`; write for that reader.
2. Draft following hard rules: inline term explanations, prose for rationale, lists only to enumerate,
   no internal codenames, references limited to code paths and official documentation URLs.
3. Order content so **why** precedes **how** (see default structure in principles reference).
4. Add narrow vertical diagrams only where they cut cognitive load (pipelines, before/after).

For `document_type: work-item-prose`, produce requirement bullets and acceptance criteria that match
the host locale and remain WHAT-not-HOW. Do not add enricher emoji sections here.

---

## PHASE 3 — GLOSSARY VERIFICATION

**Always run** when `language` is `pt-br`. **Run selectively** for `en` when the draft contains
domain terms that may need consistency checking.

Read `./references/glossary-usage.md` and load `./references/assets/tech-glossary-en-pt-br.json`.

1. Extract candidate technical terms from the draft.
2. Look up each term (exact key → `aliases` → substring scan per glossary schema).
3. For `pt-br`: replace calques with glossary `pt` values; keep repository identifiers in original
   form with a one-clause explanation.
4. For `en`: prefer glossary English keys when a term was mistranslated or anglicized incorrectly.
5. Log unresolved terms in a short **Term notes** block (chat only, not in the deliverable) when no
   glossary entry exists — propose a plain-language paraphrase instead of inventing jargon.

---

## PHASE 4 — SELF-REVIEW

Run the three sweeps from `./references/plain-language-principles.md`:

1. **Jargon sweep** — every acronym, stack term, and abbreviation explained at first use or replaced.
2. **Reference sweep** — no tickets, PRs, work-item ids, or internal session notes; code paths and
   official URLs only.
3. **Completeness check** — every completeness-contract item is present; nothing outside it was added.

Run the quality-gate checklist in the principles reference before presenting.

---

## PHASE 5 — GATE & DESTINATION

**── GATE —** WAIT for explicit approval (`proceed`, `looks good`, `publish`) before any file write.
Silence is not approval.

Then ask **where to persist** (if not already chosen):

1. **Local file** — write to the configured artifacts path, or a path the user names.
2. **Chat only** — formatted markdown ready to copy (default when invoked as a sub-pass).

When invoked **inline** from a sibling skill (`integration-notes.md`), skip this gate unless the
sibling skill is at its own persistence gate — return polished prose to the caller.

---

## Operating rules

- **Human-facing only** — dense agent instructions stay out of scope.
- **Glossary-backed translations** — never ship pt-BR with unverified calques when an entry exists.
- **Completeness over brevity** — cut topics, not sentences; preserve decisions and open questions.
- **Sub-skill mode** — when another skill calls this for a prose pass, preserve that skill's section
  headings and shape contracts; polish wording only.
- **Locale** — `en` unless the user or parent skill specifies `pt-br`.

## Examples

**Slash command:**

```
/generate-plain-language-documentation --source "OAuth tokens expire silently and users see a blank screen" --audience "feature owner" --language en --type work-item-prose
```

**Conversational trigger:**

> Document why we are replacing the legacy auth flow — make it readable for the product team

→ Infer `document_type: report`, run full pipeline.

**Sub-skill invocation (from generate-work-item PHASE 4):**

→ Polish `## Requisitos` and `## Critérios de Aceite` bullets in place; keep canonical skeleton.

**Translation:**

> Rewrite this guide in pt-BR for our Brazilian stakeholders

→ Set `language: pt-br`, run PHASE 3 glossary verification on the full draft.
