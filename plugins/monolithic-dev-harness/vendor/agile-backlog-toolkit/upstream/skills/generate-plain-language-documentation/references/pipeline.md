# generate-plain-language-documentation — Pipeline

Entry point for the skill reference library.

```
COLLECT → INGEST (completeness contract) → DRAFT → GLOSSARY VERIFY → SELF-REVIEW → GATE → DELIVER
                                              │
                                              ▼
                                    plain-language-principles.md
                                              │
                         pt-br or technical terms ──► glossary-usage.md
                                              │
                         sibling skill sub-pass ──► integration-notes.md
```

## Bundled assets

| Asset | Path |
| --- | --- |
| Tech glossary | `./references/assets/tech-glossary-en-pt-br.json` |

## Artifacts output paths (when persisting)

| Destination | Path |
| --- | --- |
| Default output | `<artifacts>/Knowledge/<kebab-slug>.md` |

## Document type map

| `document_type` | Output contract |
| --- | --- |
| `general` | `./output-formats.md` § General |
| `report` | `./output-formats.md` § Report |
| `guide` | `./output-formats.md` § Guide |
| `work-item-prose` | `./output-formats.md` § Work-item prose |

## Relationship to sibling skills

| Caller | When | What to polish |
| --- | --- | --- |
| `generate-work-item` | PHASE 4 (before present) | `## Requisitos` and `## Critérios de Aceite` bullets |
| `enrich-work-item` | PHASE 4 (after enricher) | Narrative prose inside enricher sections; not emoji labels |
| `decompose-backlog` | PHASE 3–4 (draft/enrich) | Story scope lines and enriched body narrative |

See `./integration-notes.md` for invocation contract (sub-skill mode skips standalone gate).

## Shared plugin references

- `../../references/ticket-structure.md` — when output feeds ticket drafts
