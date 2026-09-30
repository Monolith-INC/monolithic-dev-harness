# UX Contract Shapes

## DESIGN.md

Use YAML frontmatter for machine-readable design tokens where concrete values are decided:

```yaml
---
name: <design system or product>
description: <one-line posture>
status: draft | final
updated: YYYY-MM-DD
colors: {}
typography: {}
rounded: {}
spacing: {}
components: {}
sources: []
---
```

Body order when present:

1. Brand & Style
2. Colors
3. Typography
4. Layout & Spacing
5. Elevation & Depth
6. Shapes
7. Components
8. Do's and Don'ts

Reference tokens as `{colors.primary}`, `{typography.body.fontSize}`, `{rounded.md}`, or
`{spacing.4}`. When inheriting a platform or design system, name its token instead of copying the
rendered value; record only deliberate deltas.

## EXPERIENCE.md

Use this order, omitting only genuinely irrelevant sections:

1. Foundation: form factors, inherited UI system, relationship to `DESIGN.md`.
2. Information Architecture: surfaces, navigation, and ownership.
3. Voice and Tone: interface copy behavior, not visual brand prose.
4. Component Patterns: behavior, state transitions, and composition.
5. State Patterns: loading, empty, error, permission, offline, destructive, and recovery states.
6. Interaction Primitives: input, focus, feedback, motion, shortcuts, gestures.
7. Accessibility Floor: keyboard/screen-reader behavior, reduced motion, target sizes, semantics.
8. Responsive & Platform behavior when multi-surface.
9. Key Flows: stable IDs, named protagonists, ordered steps, value moment, recovery.

The two contracts own decisions. Wireframes and mocks illustrate them and must say that the
contracts win on conflict.
