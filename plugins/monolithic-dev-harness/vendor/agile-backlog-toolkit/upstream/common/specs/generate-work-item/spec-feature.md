# Feature Spec Blueprint

Blank form for specs written to **`<artifacts>/Specs/`** before the Feature ticket.

## Artifacts filename

`<parent-epic-id>-<kebab-slug>-spec.md`

## Frontmatter

```yaml
---
type: spec
work_item_type: Feature
ticket: <parent-epic-id>
area: <kebab-area>
stack: [<from-context7>]
tags: [spec, feature]
created: <YYYY-MM-DD>
source: [context7, <urls>]
---
```

## Body

```markdown
# <Title> — Feature Spec

## Objetivo (rascunho)

<1-2 paragraphs: business value and scope from description.>

## Escopo (rascunho)

### Incluído
- <Capability or area>

### Excluído
- <Out of scope>

## Critérios de sucesso (rascunho)

- [ ] <Observable business outcome>
- [ ] <Observable outcome>

## Tech stack

<Libraries/frameworks from Context7.>

## Research summary

<Distilled Context7 findings. Cite libraryId.>

## Referências

- <URL or attachment>
- Context7: `<libraryId>` — <takeaway>
- Epic: #<id>

## Open questions

- <Pending decision, or "Nenhuma">

## Descrição original

<Exact `description` input>
```
