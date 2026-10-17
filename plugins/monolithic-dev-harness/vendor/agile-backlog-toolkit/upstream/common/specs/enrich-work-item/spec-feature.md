# Feature Spec Blueprint

Blank form for specs written to **`<artifacts>/Specs/`** before the Feature ticket.

Source enricher: `../enrichers/feature-enricher.prompt.md`

## Artifacts filename

`<parent-epic-id>-<kebab-slug>-spec.md`

## Frontmatter

```yaml
---
type: spec
work_item_type: Feature
ticket: <parent-epic-id>
area: <kebab-area>
stack: [<from-context7-or-inferred-projects>]
tags: [spec, feature]
created: <YYYY-MM-DD>
source: [context7, <urls>]
feature_type: <funcional|organizacional|refatoracao>
---
```

## Body

```markdown
# <Title> — Feature Spec

## Classificação

- **Tipo de Feature:** Funcional | Organizacional | Refatoração
- **Epic pai:** #<epic-id> — <título>
- **Justificativa:** <uma linha>

## Objetivo (rascunho)

<1-2 parágrafos: valor de negócio e objetivo estratégico da Feature.>

## Escopo (rascunho)

### Incluído
- <Funcionalidade/área>

### Excluído
- <Fora do escopo>

## Critérios de sucesso (rascunho)

- [ ] <Resultado observável — negócio, não implementação>
- [ ] <Disponibilidade por plano — consultar docs de planos quando host as tiver>
- [ ] <Feature flag global `[nome]` — somente se rollout controlado/kill-switch>

## Áreas / módulos envolvidos

- <Área/módulo>
- Projeto(s): <Aplicatudo | Functions | …>

## Tech stack

<Libraries/frameworks from Context7 + code-area hints.>

## Research summary

<Distilled Context7 findings. Cite `libraryId`. Nunca inventar nomes técnicos sem verificar.>

## Análise de código (rascunho)

<Áreas do código a investigar — paths/módulos identificados por busca direcionada, não suposição.>

## Referências

- <URL ou doc>
- Context7: `<libraryId>` — <takeaway>
- Epic: #<id>

## Open questions

- <Decisão pendente, ou "Nenhuma">

## Descrição original

<Texto exato do `idea` input>
```

## Ticket drafting rules (from enricher)

**Never:** prescrever implementação; critérios de aceite de Stories; breakdown/estimativa; repetir
entre seções.

**Always:** valor de negócio, escopo, critérios mensuráveis, áreas/módulos. Máximo **300 palavras**
no ticket (excl. Descrição Original). Português BR.

Ticket body: `enrichers/feature-enricher.prompt.md` §4.
