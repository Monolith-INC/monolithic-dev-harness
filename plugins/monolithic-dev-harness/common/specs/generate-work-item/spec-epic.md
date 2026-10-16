# Epic Spec Blueprint

Blank form for specs written to **the item's folder in the artifacts path** before the Epic ticket. Context7 research
feeds **Tech stack** and **Research summary**.

## Artifacts filename

`spec-<scope>.md`, from `harness document path --type spec` (see `references/document-layout.md`)

## Frontmatter

```yaml
---
type: spec
work_item_type: Epic
ticket: null
area: <kebab-area>
stack: [<from-context7-or-inferred>]
tags: [spec, epic]
created: <YYYY-MM-DD>
source: [context7, <urls>]
---
```

## Body

```markdown
# <Title> — Epic Spec

## Problema / oportunidade

<Clear business problem or opportunity from description.>

## Objetivos (rascunho)

- <Measurable strategic outcome>
- <Measurable strategic outcome>

## Escopo (rascunho)

### Incluído
- <Area or capability>

### Excluído
- <Out of scope for this Epic>

## Tech stack

<Libraries/frameworks from Context7 + inferred stack.>

## Research summary

<Distilled Context7 findings — constraints, patterns. Cite libraryId.>

## Referências

- <URL or attachment>
- Context7: `<libraryId>` — <takeaway>

## Open questions

- <Pending decision, or "Nenhuma">

## Descrição original

<Exact `description` input>
```
