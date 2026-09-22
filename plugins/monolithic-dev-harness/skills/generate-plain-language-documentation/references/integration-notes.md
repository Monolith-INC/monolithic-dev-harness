# Integration Notes

How sibling Agile Backlog Toolkit skills delegate prose to `generate-plain-language-documentation`.

## Invocation modes

| Mode | Gate | Return |
| --- | --- | --- |
| **Standalone** | PHASE 5 gate before local write | Full document to user |
| **Sub-skill** | Caller skill's gate only | Polished sections in place |

Sub-skill mode: read this skill's PHASE 2–4 instructions; skip PHASE 0 when caller already collected
inputs; skip standalone PHASE 5 gate.

---

## generate-work-item

**Hook:** PHASE 4 — GENERATE DRAFT, after bullets are drafted, before present.

1. Draft per `generate-work-item/references/output-formats.md`.
2. Run a **work-item-prose** sub-pass on `## Requisitos` and `## Critérios de Aceite`.
3. Match locale of input `description` (pt-BR labels when description is Portuguese).
4. Run glossary verification when locale is pt-BR.
5. Continue to PHASE 5 gate with polished draft.

Do not change `# Title`, spec wikilink, or section heading names required by canonical templates.

---

## enrich-work-item

**Hook:** PHASE 4 — ENRICH, after enricher output is assembled, before checklist and present.

1. Apply enricher rules first — enricher § output format is authoritative for structure.
2. Run a sub-pass on narrative paragraphs inside each section (not emoji headings).
3. Keep **Descrição Original** verbatim — do not plain-language the original-ingest block.
4. Glossary-verify when host enrichers are pt-BR.
5. Run enricher **Checklist de Auto-Revisão** after prose polish.

---

## decompose-backlog

**Hook:** PHASE 3 — DRAFT and PHASE 4 — ENRICH.

1. **DRAFT:** polish one-line scope lines and section prose per `canonical-user-story.md`.
2. **ENRICH:** same sub-pass as enrich-work-item on enriched story bodies (narrative paragraphs only).
3. Preserve story-point driver tables and emoji section order.
4. Glossary-verify via `./references/assets/tech-glossary-en-pt-br.json` when locale is pt-BR (see
   `glossary-usage.md`).

---

## Triggering from host

Registered as `/generate-plain-language-documentation` via plugin skill discovery (`skills/` symlink
and `skills.sh.json`). Description is intentionally broad so any documentation or prose-writing
request activates this skill even when the user does not name it.
