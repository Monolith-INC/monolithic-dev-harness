# Decomposition Rules

Self-contained rules for splitting a parent work item into Stories. These travel with the skill
so it needs no host-repo docs to function.

## Backlog hierarchy

```
Epic
  └─ Feature
       └─ Story  (User Story / Bug / Tech Debt / Spike)  ← the unit you create here
            └─ Task
```

- A **Story** is executable work that fits one sprint and yields exactly **1 Pull Request**.
  "Story" covers User Story, Bug, Tech Debt, Spike — same backlog rules.
- A Story's parent is its **Feature**, never the Epic directly.

## The sizing rule (the core judgment)

**1 Story = 1 sprint = 1 PR.** Split the parent so each Story honors this. If a candidate Story
would exceed the team's story-point ceiling (default ceiling: **5 points** — confirm with the host
team), split it further, or stage it into phases and carry later phases as separate Stories.

Each Story must trace to a **verbatim slice of the parent text**. If a slice has no Story, it is a
dropped requirement (caught in AUDIT). If a Story has no parent slice, it is scope creep.

## Story-point heuristic (6-driver MAX)

Score each driver 1/2/3/5/8; the Story's points = the **MAX** across drivers (not the sum). This
keeps one hard dimension from being diluted by easy ones.

| Driver       | 1                | 2                  | 3                       | 5                          | 8                        |
|--------------|------------------|--------------------|-------------------------|----------------------------|--------------------------|
| Escopo       | one tiny change  | one area           | multiple artifacts/area | multiple areas             | cross-project/refactor   |
| Incerteza    | known            | mostly known       | some unknowns           | significant unknowns       | PoC + iterations         |
| Integrações  | none             | one stable         | a couple to integrate   | many / unstable            | several new / high risk  |
| Dados        | none             | trivial            | some shaping            | complex modeling/migration | needs downtime window    |
| QA           | trivial          | unit-level         | a flow                  | multi-screen E2E journey   | extensive regression     |
| Rollout      | none             | flag/simple        | coordinated             | risky/irreversible         | complex rollback/multi-team |

**MAX has no exceptions** — two drivers at 5 is a 5-point Story, not an 8-point one.

Record the per-driver scores and the MAX in the Story's Complexity section so the estimate is
auditable, e.g. `5 pts — driver: QA=5 (multi-screen E2E); Escopo=5; rest ≤3`.

Points size a Story; they are not a duration. For turning points into hours, see `estimation.md`.

## Definition of Ready (each Story must meet)

- [ ] Title states a clear objective (describe the need, not the solution; for Bugs, the defect).
- [ ] Detailed description (behaviors, scenarios, technical specs, affected areas).
- [ ] Story points set.
- [ ] Linked to a Feature.

## Feature sizing rule (Epic → Feature)

A **Feature** is one coherent capability of the Epic that the Feature Owner can demo and PO/PM can
validate as a unit (the unit of a Feature Demo Interna). Sizing:

- Each Feature traces to a **verbatim slice of the Epic text**. A slice with no Feature is a dropped
  requirement; a Feature with no slice is scope creep.
- A Feature holds **2–6 Stories** (default; confirm with the host team). More than 6 → split the
  Feature. Exactly 1 → it is a Story: fold it into the sibling Feature it depends on most.
- Features are cut along user-visible capability, not along layers. "Backend for X" / "UI for X"
  is a layer split: merge them and let the Stories carry the layers.
- Features carry no points. Their size is the sum of their Stories.

## Parent-type branch

- Parent is a **Feature** → *story mode*: decompose straight into Stories.
- Parent is an **Epic** → *tree mode*: decompose into Features, and each Feature into Stories, in
  **one run with the same two gates**. The Epic's existing child Features (from its relations)
  are listed in the proposal and reused where they fit; new Features are proposed only for slices
  no existing Feature covers.
- Never attach a Story directly to an Epic, in either mode.

## Provenance

Distilled from the originating team's `development-process.md` (hierarchy, DoR, story points) and
backlog-strategy guides. Values marked "default" / "confirm with host team" are tunable seams.
