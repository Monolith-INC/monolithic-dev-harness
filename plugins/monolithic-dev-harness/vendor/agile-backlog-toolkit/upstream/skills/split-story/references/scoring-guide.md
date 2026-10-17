# Scoring Guide

Reference for the `split-story` skill SCORE phase. Covers the 6-driver MAX heuristic,
story-point ceiling, spike detection, and discrepancy handling.

## 6-Driver MAX Heuristic

Score each driver independently on the 1/2/3/5/8 scale. The story's calculated points =
the **MAX** across all drivers (not the sum). This ensures one hard dimension cannot be
diluted by easy ones.

| Driver | 1 | 2 | 3 | 5 | 8 |
|---|---|---|---|---|---|
| **Escopo** | One tiny, isolated change | One area or module | Multiple artifacts or one complex area | Multiple areas or significant cross-cutting scope | Cross-project or extensive refactor |
| **Incerteza** | Fully known — clear spec, no research needed | Mostly known — minor unknowns resolvable in breakdown | Some meaningful unknowns — may need spike or tech research | Significant unknowns — direction unclear; investigation required before implementation | Proof-of-concept plus iterations before the work can be scoped |
| **Integrações** | No integrations | One stable, well-documented integration | A couple of integrations to coordinate | Many integrations or one unstable / undocumented integration | Several new integrations, or one high-risk contract |
| **Dados** | No data concerns | Trivial data (simple fields, no migration) | Some data shaping (schema change, mapping) | Complex modeling or data migration | Migration needing a maintenance window or downtime |
| **QA** | Trivial — no meaningful test scenarios | Unit-level coverage only | One distinct user flow to test | Multi-screen E2E journey or complex state combinations | Extensive regression or a dedicated E2E suite |
| **Rollout** | No rollout concerns | Simple feature flag or config toggle | Coordinated rollout (multiple environments / teams) | Risky or irreversible rollout (data migration, external API, billing) | Complex rollback, or coordination across multiple teams |

**MAX has no exceptions.** Two drivers at 5 is still a 5-point story, not an 8-point one. If two
dimensions are genuinely hard, that shows up in the split decision below, not by inflating the score.

### How to Score

1. For each driver, pick the score that best matches the story as written.
2. Record all six scores.
3. `calculated_points = MAX(Escopo, Incerteza, Integrações, Dados, QA, Rollout)`.
4. Note which driver(s) are at the MAX — this is the dominant driver(s).

### Recording Format

Use this format in the story's `📊 Complexidade` section:

```text
5 pts — driver: QA=5 (multi-screen E2E); Incerteza=3; Escopo=3; rest ≤2
```

Always state which driver set the MAX and the brief reason why.

---

## Story-Point Ceiling

**Default ceiling: 5 points.**

If `calculated_points ≤ ceiling`: the story is right-sized. No split needed (ANALYZE Branch A).

If `calculated_points > ceiling`: split is required.
`split_count = ⌈calculated_points / ceiling⌉`.

The ceiling is overridable per invocation via an optional argument. If the user passes a
ceiling override, use it instead of 5.

---

## Spike Detection Rule

**Condition:** `Incerteza == 5` AND Incerteza is the sole MAX driver (no other driver also
scored 5).

**Recommendation:** Do NOT split the story by scope. Scope-splitting does not reduce
uncertainty — it just produces multiple uncertain stories. Instead, recommend a Spike:
a time-boxed investigation story that produces a decision or proof-of-concept.

**Spike stub format (when user confirms):**

```markdown
**🎯 O quê**
Investigar [the unknown aspect] para determinar [what decision or output is needed].

**💡 Por quê**
A incerteza elevada nesta história impede uma estimativa confiável e aumenta o risco de
retrabalho.

**📋 Comportamento esperado**
Ao final do spike, a equipe tem: [specific deliverable — e.g., "a documented approach and
updated estimate for the original story"].

**✅ Critérios de Aceite**
- [ ] [Specific question 1 answered with documented evidence]
- [ ] [Specific question 2 answered with documented evidence]
- [ ] Original story re-estimated and ready for next sprint.

**🔧 Notas Técnicas**
Time-box: [team's default spike duration — e.g., 1 sprint or 2 days].

**📊 Complexidade**
3 pts — driver: Escopo=3 (spike output = decision doc + re-estimate); Incerteza=1
(investigation itself is bounded).

**📄 Descrição Original**
[Verbatim slice of the original story that triggered the spike recommendation.]
```

When drafting a Spike stub, fill each `[placeholder]` with content derived from the original
story's description and the specific unknown that caused `Incerteza=5`.

---

## Discrepancy Handling

A discrepancy occurs when the story has a declared story-point value (from frontmatter
`story_points` or Azure `Microsoft.VSTS.Scheduling.StoryPoints`) that differs from
`calculated_points`.

### Protocol

1. **Show both values** with the full driver breakdown for the calculated value.
2. **Do not auto-resolve.** Always ask the user which value to trust.
3. **Present exactly this prompt:**

```text
Story points discrepancy detected.

Declared:   <X> pts  (from <source: frontmatter | Azure>)
Calculated: <Y> pts  (MAX driver: <driver>=<score> — <reason>)

Driver breakdown:
  Escopo:      <score>
  Incerteza:   <score>
  Integrações: <score>
  Dados:       <score>
  QA:          <score>
  Rollout:     <score>

Which value should be used for the split decision?
  1. Declared (<X> pts)
  2. Calculated (<Y> pts)
```

4. Wait for user input. Proceed with `active_points = user's chosen value`.

### When declared and calculated agree

If `declared_points == calculated_points`: no prompt shown. Proceed with
`active_points = declared_points`.

### When story points are not declared

If no story points are declared in any source: skip the discrepancy check entirely. Proceed
with `active_points = calculated_points`.
