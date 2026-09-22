# User Story Spec Blueprint

Blank form for specs written to **`<artifacts>/Specs/`** before the User Story ticket.

## Artifacts filename

`<parent-feature-id>-<kebab-slug>-spec.md`

## Frontmatter

```yaml
---
type: spec
work_item_type: User Story
ticket: <parent-feature-id>
area: <kebab-area>
stack: [<from-context7>]
tags: [spec, user-story]
created: <YYYY-MM-DD>
source: [context7, <urls>]
---
```

## Body

```markdown
# <Title> — Work Item Spec

## Problema / necessidade

<Restate description in 1-2 sentences.>

## Dados técnicos a preservar

<Explicit names from description that must appear in the ticket.>

## Comportamento esperado (rascunho)

- <Observable behavior or rule>
- <Another behavior>

## Tech stack

<Libraries/frameworks from Context7.>

## Research summary

<Distilled Context7 findings. Cite libraryId.>

## Critérios de aceite (rascunho)

- [ ] <Testable outcome>
- [ ] <Testable outcome>

## Referências

- <URL or attachment>
- Context7: `<libraryId>` — <takeaway>

## Open questions

- <Pending decision, or "Nenhuma">

## Descrição original

<Exact `description` input>
```
