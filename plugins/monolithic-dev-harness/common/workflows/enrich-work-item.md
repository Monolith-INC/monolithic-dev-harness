# enrich-work-item — Pipeline

Entry point for the enrichment reference library.

```
COLLECT → INGEST → ROUTE ENRICHER → [WRITE SPEC] → ENRICH → GATE → PERSIST
         │              │                              │
         │              ▼                              ▼
         │        enrichers/*.prompt.md         exact enricher output
         └─ source url | path | text
              │
              ├─ tracker id/link → tracker_get_work_item (work item + attachments + refs)
              ├─ artifacts path/filesystem path → Read verbatim
              └─ pasted text → use as description
```

## Type map

| `work_item_type` | Enricher | Spec blueprint | Canonical template | Example |
| --- | --- | --- | --- | --- |
| `epic` | `enrichers/epic-enricher.prompt.md` | `../specs/enrich-work-item/spec-epic.md` | `../templates/canonical-epic.md` | `../../skills/enrich-work-item/references/examples/example-epic.md` |
| `feature` | `enrichers/feature-enricher.prompt.md` | `../specs/enrich-work-item/spec-feature.md` | `../templates/canonical-feature.md` | `../../skills/enrich-work-item/references/examples/example-feature.md` |
| `user-story` | `enrichers/work-item-enricher.prompt.md` | `../specs/enrich-work-item/spec-work-item.md` | `../templates/canonical-user-story.md` | `../../skills/enrich-work-item/references/examples/example-user-story.md` |
| `task` | `enrichers/task-enricher.prompt.md` | `../specs/enrich-work-item/spec-work-item.md` | `../templates/canonical-task.md` | — |

Enricher prompts are bundled under `./enrichers/` — authoritative; no local override.

## Artifacts output paths (when persisting to artifacts path)

**Spec** (optional): `harness document path --type spec …` (`../../references/document-layout.md`)

**Enriched draft**: `Tickets/Ready/<prefix>-<kebab-slug>.md` (default; adapt to host layout)

## Shared plugin references

- `../../references/decomposition-rules.md` — hierarchy, story-point heuristic
- `../../references/ticket-structure.md` — draft file constraints
- `../providers.md` — writing to the selected tracker

## Relationship to generate-work-item

| Skill | Input | Output |
| --- | --- | --- |
| `generate-work-item` | title + description | Raw `# Title` + `## Requisitos` + `## Critérios de Aceite` |
| `enrich-work-item` | existing source text | Enricher emoji-section format per type |

Typical flow: generate raw draft → plain-language prose pass → enrich to team format → create in the tracker.

| Skill | Prose role |
| --- | --- |
| `generate-plain-language-documentation` | Plain-language bullets and narrative (standalone or sub-pass) |
