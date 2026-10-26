# Epic Spec Blueprint

Blank form for specs written to **`<artifacts>/Specs/`** before the Epic ticket. Context7 research
feeds **Tech stack** and **Research summary**; strategic content feeds the Epic ticket body.

Source enricher: `../enrichers/epic-enricher.prompt.md`

## Artifacts filename

`[<epic-id>-]<kebab-slug>-spec.md`

## Frontmatter

```yaml
---
type: spec
work_item_type: Epic
ticket: null
area: <kebab-area>
stack: [<from-context7-or-inferred-projects>]
tags: [spec, epic]
created: <YYYY-MM-DD>
source: [context7, <urls>]
epic_type: <produto|melhoria|tecnico|organizacional>
---
```

## Body

```markdown
# <Title> — Epic Spec

## Classificação

- **Tipo de Epic:** Produto | Melhoria | Técnico | Organizacional
- **Justificativa:** <uma linha>

## Problema de negócio

<Descrição clara do problema ou oportunidade — alimenta 📊 Problema de Negócio no ticket.>

## Visão estratégica (rascunho)

<2-3 frases: problema, objetivo de longo prazo, valor esperado.>

## Objetivos estratégicos (rascunho)

- <Objetivo mensurável — resultado de negócio>
- <Objetivo mensurável>

## Métricas de sucesso (rascunho KPIs/OKRs)

- <Métrica com baseline → meta>
- <Métrica com baseline → meta>

## Escopo estratégico (rascunho)

### Incluído
- <Área/funcionalidade>

### Excluído
- <Fora do escopo neste Epic>

## Áreas / projetos envolvidos

- <Módulo/área>
- Projetos: <Aplicatudo | Functions | bHave Admin | bhaviews | …>

## Tech stack

<Libraries/frameworks from Context7 + inferred stack from idea/refs.>

## Research summary

<Distilled Context7 findings — constraints, patterns, APIs. Cite `libraryId`.>

## Dependências e riscos estratégicos

- <Dependência ou risco>
- <Dependência ou risco>

## Referências

- <URL ou doc externo>
- Context7: `<libraryId>` — <takeaway>
- Parent/context: <se aplicável>

## Open questions

- <Decisão pendente, ou "Nenhuma">

## Descrição original

<Texto exato do `idea` input>
```

## Ticket drafting rules (from enricher)

**Never:** prescrever implementação; detalhar Features/Stories; estimar esforço/pontos; repetir
entre seções.

**Always:** objetivos estratégicos, problema de negócio, KPIs. Máximo **400 palavras** no ticket
(excl. Descrição Original). Português BR.

Ticket body: `enrichers/epic-enricher.prompt.md` §4.
