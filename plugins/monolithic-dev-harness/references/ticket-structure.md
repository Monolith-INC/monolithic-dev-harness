# Ticket Structure & Draft Constraints

How each artifact draft is written so it passes the host contract and carries the exact body sent
to a selected provider.

## Draft location (configurable seam)

Default: `Tickets/Ready/` under the configured artifacts path. If the host organizes drafts elsewhere, adapt — this
is a default, not a hard requirement.

## Frontmatter (hook-validated)

```yaml
---
date: <YYYY-MM-DD>
type: ticket            # REQUIRED — the frontmatter hook rejects drafts missing `type`
work_item_type: <Epic|Feature|User Story|Task>
provider: <local|azure-devops|linear>
provider_id: "<provider identifier; omit before provider creation>"
parent_id: "<immediate parent identifier; omit for Epic>"
story_points: <number>  # REQUIRED for User Story — the validator fails a draft without it
effort_hours: <number>  # optional — estimated duration; omit when nobody has estimated it
activity: Development   # optional — capacity activity bucket (Azure `Microsoft.VSTS.Common.Activity`)
iteration: <sprint-ref> # optional — used by capacity planning to scope a sprint
language: pt-BR         # optional — en | pt-BR, default pt-BR; selects which section-label set
                         # the validator checks the body against (see Body sections below)
tags: [ticket, user-story, ...]
---
```

**On `effort_hours`:** for a Task this is derived from the parent Story's points and kept current
automatically — see `estimation.md`. Written by hand it is equally valid; either way an absent
value is an honest state and the validator treats it as `SKIP`.

**Hard constraint:** do NOT include a `status:` key — the draft contract forbids `status`
in `Tickets/`. Lifecycle lives in the selected provider, not in frontmatter.

## Filename (hook-validated)

Regex: `^(\d+|tech-debt|bug|task|spike)-[a-z0-9-]+`, all lowercase.

Until a provider assigns the real id, prefix with the immediate parent id (for example,
`6868-us1-...`). After creation, rename with the provider identifier and set `provider_id`.
Provider identifiers and `parent_id` are strings. Legacy keys `azure_id`, `parent_feature`, and
`parent_epic` are invalid.

## Body sections (order)

The body is written once and becomes the provider description verbatim. Section labels follow the
draft's `language:` frontmatter value — **the validator matches on the exact label for that
language**, so pick one and set the frontmatter key accordingly; do not mix labels from both
columns in one draft.

| # | pt-BR (default) | en | Purpose |
|---|---|---|---|
| 1 | 🎯 O quê | 🎯 What | What, as descriptive sentences, one idea per line. |
| 2 | 💡 Por quê | 💡 Why | Why this Story exists. |
| 3 | 📋 Comportamento esperado | 📋 Expected Behavior | Expected behavior; ASCII diagrams here (see azure-mechanics.md). |
| 4 | ✅ Critérios de Aceite | ✅ Acceptance Criteria | Acceptance criteria as checkboxes. |
| 5 | 🔧 Notas Técnicas | 🔧 Technical Notes | Technical notes; areas/modules, not invented implementation. |
| 6 | 📊 Complexidade | 📊 Complexity | Story points + the per-driver MAX justification (decomposition-rules.md). |
| 7 | 📄 Descrição Original | 📄 Original Description | The verbatim parent slice this Story traces to. |

The 6-driver story-point heuristic names (decomposition-rules.md) also localize:

| pt-BR | en |
|---|---|
| Escopo | Scope |
| Incerteza | Uncertainty |
| Integrações | Integrations |
| Dados | Data |
| QA | QA |
| Rollout | Rollout |

## Content hygiene

- State each fact ONCE, in its natural section. No repetition across sections.
- No machine-specific paths or local-only / spike folder references; the project repo is the
  canonical root.
- Locale-correct technical vocabulary; no calques from English.
- No decision-making/meta in the body. An unresolved choice becomes an `@TODO (decide in breakdown)`
  annotation, never prose pretending to be a requirement.
- Focus on the WHAT and WHERE (area/module), never invent the HOW.
