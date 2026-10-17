# enrich-work-item — Pipeline

Entry point for the enrichment reference library.

```
COLLECT → INGEST → ROUTE ENRICHER → [WRITE SPEC] → ENRICH → GATE → PERSIST
         │              │                              │
         │              ▼                              ▼
         │        enrichers/*.prompt.md         exact enricher output
         └─ source url | path | text
              │
              ├─ Azure URL/id → azure-ingest.md (work item + attachments + refs)
              ├─ artifacts path/filesystem path → Read verbatim
              └─ pasted text → use as description
```

## Type map

| `work_item_type` | Enricher | Spec blueprint | Canonical template | Example |
| --- | --- | --- | --- | --- |
| `epic` | `enrichers/epic-enricher.prompt.md` | `blueprints/spec-epic.md` | `../templates/canonical-epic.md` | `examples/example-epic.md` |
| `feature` | `enrichers/feature-enricher.prompt.md` | `blueprints/spec-feature.md` | `../templates/canonical-feature.md` | `examples/example-feature.md` |
| `user-story` | `enrichers/work-item-enricher.prompt.md` | `blueprints/spec-work-item.md` | `../templates/canonical-user-story.md` | `examples/example-user-story.md` |
| `task` | `enrichers/task-enricher.prompt.md` | `../specs/enrich-work-item/spec-work-item.md` | `../templates/canonical-task.md` | — |

Enricher prompts are bundled under `./enrichers/` — authoritative; no local override.

## Artifacts output paths (when persisting to artifacts path)

**Spec** (optional): `<artifacts>/Specs/[<parent-id>-]<kebab-slug>-spec.md`

**Enriched draft**: `<artifacts>/Tickets/Ready/<prefix>-<kebab-slug>.md` (default; adapt to host layout)

## Shared plugin references

- `../../references/decomposition-rules.md` — hierarchy, story-point heuristic
- `../../references/ticket-structure.md` — draft file constraints
- `../providers.md` — local, Azure DevOps, and Linear persistence

## Relationship to generate-work-item

| Skill | Input | Output |
| --- | --- | --- |
| `generate-work-item` | title + description | Raw `# Title` + `## Requisitos` + `## Critérios de Aceite` |
| `enrich-work-item` | existing source text | Enricher emoji-section format per type |

Typical flow: generate raw draft → plain-language prose pass → enrich to team format → create in Azure.

| Skill | Prose role |
| --- | --- |
| `generate-plain-language-documentation` | Plain-language bullets and narrative (standalone or sub-pass) |
