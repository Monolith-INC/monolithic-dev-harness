# enrich-work-item — Output Formats

Each work-item type uses the **enricher** as the authoritative output contract. This file routes to
the right enricher section — do not invent alternate layouts.

`generate-work-item` delegates requirement and acceptance-criteria prose to
`generate-plain-language-documentation` using the `work-item-prose` format before it presents a draft.

## Canonical templates (read-only)

Shape contracts are the sibling files in this directory — **do not edit** them:

| Type | Template |
| --- | --- |
| `epic` | `canonical-epic.md` |
| `feature` | `canonical-feature.md` |
| `user-story` | `canonical-user-story.md` |
| `task` | `canonical-task.md` |

Validate enriched output against the matching template before presenting.

## Routing table

| Type | Enricher file | Output section | Word budget (excl. Descrição Original) |
| --- | --- | --- | --- |
| `epic` | `enrichers/epic-enricher.prompt.md` | §4 Formato de Saída | 400 |
| `feature` | `enrichers/feature-enricher.prompt.md` | §4 Formato de Saída | 300 |
| `user-story` | `enrichers/work-item-enricher.prompt.md` | §6 Formato de Saída | 200 (+ Comportamento esperado, Anexos) |
| `task` | `../../workflows/enrichers/task-enricher.prompt.md` | §4 Formato de Saída | 150 |

## Epic sections (from enricher)

`## 🎯 Visão Estratégica`, `## 📊 Problema de Negócio`, `## 🎯 Objetivos Estratégicos`,
`## 📈 Métricas de Sucesso (KPIs/OKRs)`, `## 📦 Escopo Estratégico`, `## 🔧 Áreas/Projetos Envolvidos`,
`## 🔗 Dependências e Riscos Estratégicos`, `## 📄 Descrição Original`

## Feature sections (from enricher)

`## 🎯 Objetivo`, `## 📦 Escopo`, `## ✅ Critérios de Sucesso`, `## 🔧 Áreas/Módulos Envolvidos`,
`## 📄 Descrição Original`

## User Story sections (from enricher)

`## 🎯 O quê`, `## 💡 Por quê`, optional `## 📋 Comportamento esperado`, `## ✅ Critérios de Aceite`,
optional `## 🔧 Notas Técnicas`, optional `## 🔄 Como Reproduzir` (bugs), `## 📊 Complexidade`,
optional `## 📎 Anexos / Referências`, `## 📄 Descrição Original`

## Task sections (from enricher)

`## 🎯 Resultado`, `## 🔧 Trabalho`, `## ✅ Verificação`, `## 📄 Descrição Original`

## Quality gates (all types)

- Run enricher **Checklist de Auto-Revisão** before presenting.
- Omit empty or inapplicable sections.
- ASCII diagrams in Comportamento esperado or Notas Técnicas when the enricher calls for them.
- Story points: 6-driver MAX heuristic from `decomposition-rules.md` in `## 📊 Complexidade`.

## Canonical examples

Illustrative dummy outputs (content patterns only — **not** the shape contract):

- `examples/example-epic.md`
- `examples/example-feature.md`
- `examples/example-user-story.md`

Shape contracts: `canonical-*.md` (read-only; see above).

## Provider description

When persisting to Azure DevOps or Linear, the enriched body becomes the provider item description
in **Markdown** format.
