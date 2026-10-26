# Work Item Spec Blueprint

Blank form for specs written to **`<artifacts>/Specs/`** before User Story, Bug, or Task tickets.

Source enricher: `../enrichers/work-item-enricher.prompt.md`

## Artifacts filename

`<parent-feature-id>-<kebab-slug>-spec.md` (or `task-<slug>-spec.md` for orphan tasks)

## Frontmatter

```yaml
---
type: spec
work_item_type: <User Story|Bug|Task>
ticket: <parent-id>
area: <kebab-area>
stack: [<from-context7>]
tags: [spec, user-story|bug|task]
created: <YYYY-MM-DD>
source: [context7, <urls>]
classification: <user-story|bug|task>
---
```

## Body

```markdown
# <Title> — Work Item Spec

## Classificação

- **Tipo:** User Story | Bug | Task
- **Sinais:** <palavras-chave que levaram à classificação>
- **Feature pai:** #<feature-id> — <título> (quando aplicável)
- **Story pai:** #<story-id> (somente para Task)

## Problema / necessidade

<Restate o `idea` em 1-2 frases.>

## Dados técnicos a preservar

<Nomes explícitos da descrição original que DEVEM aparecer no ticket.>

## Requisitos implícitos (análise)

| Categoria | Requisitos essenciais inferidos |
| --- | --- |
| <UI / Formulário / Async / …> | <loading, validação, empty state, …> |

## Comportamento esperado (rascunho)

#### <Fluxo ou bloco>
- <Regra ou condição>

## Tech stack

<Libraries/frameworks from Context7.>

## Research summary

<Distilled Context7 findings. Cite `libraryId`.>

## Áreas de código

<Módulos/arquivos — ONDE, não COMO.>

## Complexidade (pré-avaliação)

| Driver | Score (1/2/3/5/8) | Nota |
| --- | --- | --- |
| Escopo | | |
| Incerteza | | |
| Integrações | | |
| Dados | | |
| QA/Regressão | | |
| Rollout | | |

**Maior driver:** <n> → **<pontos> pontos**

## Critérios de aceite (rascunho)

- [ ] <Alto nível, testável>
- [ ] <Verbos no infinitivo>

## Referências

- <URL ou doc>
- Context7: `<libraryId>` — <takeaway>

## Open questions

- <Decisão pendente, ou "Nenhuma">

## Descrição original

<Texto exato do `idea` input>
```

## Classification keywords (enricher §1)

- **Bug:** erro, falha, crash, não funciona, quebrado, exceção, comportamento incorreto
- **User Story:** novo, adicionar, implementar, criar, permitir, refatorar, atualizar, configurar,
  migrar, documentar, melhorar
- **Task:** parent Story scope or explicit `task` argument

## Ticket drafting rules (from enricher)

**Never:** prescrever implementação não na descrição original; critérios óbvios; apagar nomes
técnicos do autor.

**Always:** O QUÊ not COMO; ONDE (área/módulo). Máximo **200 palavras** no ticket (excl.
Descrição Original, Comportamento esperado, Anexos). Português BR.

Ticket body: `enrichers/work-item-enricher.prompt.md` §6.
