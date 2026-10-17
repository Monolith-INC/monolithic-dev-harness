# Output Formats

Deliverable shapes by `document_type`. All types inherit hard rules from
`./plain-language-principles.md`.

## General

Free-form markdown document following the default structure in principles. Suitable for one-off
rewrites.

```markdown
# <Title>

<Body per default structure — adapt sections to source material>
```

## Report

Decision or status report for stakeholders.

```markdown
# <Title>

## What this document is

## Background

## Problems and evidence

### <Problem name>

<prose>

- <evidence bullet>

## Core idea

## Changes

## Out of scope

## Delivery plan

## Decisions to record

## Open questions
```

## Guide

How-to or onboarding document.

```markdown
# <Title>

## What this guide covers

## Prerequisites

## Steps

### <Step name>

<prose>

1. <enumerated action>

## Troubleshooting

## References (code and official docs only)
```

## Work-item prose

Requirement bullets and acceptance criteria for sibling skills. **Preserves caller section headings**
— does not add enricher emoji blocks.

```markdown
## Requisitos

- <WHAT-not-HOW requirement — plain language>

## Critérios de Aceite

- [ ] <Testable outcome — infinitive verb>
```

For English host teams, use `## Requirements` and `## Acceptance Criteria` when the parent skill
locale is `en`.

### Sub-skill contract

- Input: draft bullets or narrative from caller skill.
- Output: same headings and checkbox syntax; polished wording only.
- Do not change canonical skeleton enforced by `generate-work-item` or enricher § output format.
