---
name: review-maintainability
description: Maintainability quality lens for changed code: structural simplification, boundary ownership, atomicity, orchestration, and abstraction. Invokable standalone or via --lenses maintainability|all on lifecycle review skills; never runs silently.
---

# Review Maintainability

Use this skill for a maintainability review. The agent invokes it when the user passes `--lenses maintainability` or `--lenses all` on a lifecycle review, or when run standalone. It is a
strictly read-only quality lens: it changes no source, working-tree file, Git object, index,
remote, pull request, comment, tracker record, or persisted review state. Reading the project
knowledge store is not a mutation and is permitted; its write operations are not.

It never runs silently during lifecycle review. When embedded, merge only `VERIFIED` findings into the parent report lens subsection. Do not turn generic polish into findings. The review boundary is the
changed scope the user identifies or the agreed diff range; unchanged code may be read only as
context for a changed-line finding.

## Project knowledge

When `.monolithic-code-review/sources.json` records a `knowledge.root`, read the documented
structure before judging the changed structure. Follow the cost ladder — routing table, then search,
then one unit — and never read the whole store.

- `2-structure/architecture` — layers, dependency rules, and key abstractions. This is what turns a
  boundary-ownership finding from an inference about intent into a check against a stated rule.
- `2-structure/domain-model` — entities, invariants, and bounded contexts, for deciding which layer
  legitimately owns a rule.

Cite the unit `id` when a finding rests on it, and apply the same provenance gate as every other
skill: `derived` and `stated` units support a finding, `assumed` units are `INCONCLUSIVE` and stay
in local uncertainty. Where the documented architecture and the code disagree and the code is
right, report the drift under local uncertainty rather than holding the diff to a stale rule.

## Procedure

### 1. Establish the changed scope without mutation

Ask for the base and target when they are not unambiguous. Use only read-only commands, such as:

```bash
git status --short
git diff --stat <base>...<target>
git diff --name-status <base>...<target>
git diff <base>...<target>
```

Read changed files in full and the immediate callers, callees, and boundary interfaces needed to
test a claim. Treat pre-existing modified or untracked paths as user-owned: report their status
only when relevant to the stated boundary; never clean, stage, stash, or alter them.

### 2. Test structural claims, not preferences

Inspect changed behavior against these concerns. A concern is a prompt to investigate, never an
automatic finding.

| Concern | Look for | Finding threshold |
| --- | --- | --- |
| Structural simplification | A changed branch, wrapper, mode, layer, or duplicate path that can be removed while preserving the demonstrated contract. | Cite the redundant structure, its callers, and a smaller credible design. |
| Boundary ownership | Domain rules, validation, policy, or side effects owned by the wrong layer or leaking across a changed boundary. | Show the crossing and the concrete duplicated, bypassed, or inconsistent outcome. |
| Atomicity | A changed state transition or side-effect sequence that can leave observable partial state. | Give the interruption/failure trace and the inconsistent state it permits. |
| Orchestration | Unnecessary sequential work, scattered coordination, or a changed flow that hides ordering, cancellation, or error ownership. | Show the actual dependency/order and the latency, failure, or control-flow consequence. |
| Abstraction | A changed interface or helper that obscures a meaningful contract, duplicates a concept, or forces callers through needless indirection. | Name the callers affected and the concrete comprehension or correctness cost. |

Do not use file line count as an automatic blocker. Size can trigger inspection only; report it
only when evidence establishes one of the structural consequences above. Do not report naming,
formatting, stylistic preferences, or generic lifecycle-review polish.

### 3. Record evidence and decide disposition

For every material candidate, create an evidence record with: `id`, falsifiable `claim`, expected
structural invariant, decisive `evidence`, and, when a comparison is made, comparable `baseline`
and `treatment`; include `confounds` when access or context prevents a reliable decision.

| Verdict | Meaning | Disposition |
| --- | --- | --- |
| `VERIFIED` | Evidence supports the claim and the stated invariant. | `report` |
| `NOT VERIFIED` | Evidence contradicts the claim or shows no stated consequence. | `drop` |
| `INCONCLUSIVE` | Missing or invalid access, baseline, or execution evidence prevents a decision. | `local-uncertainty` |

Only `VERIFIED` candidates become findings. `NOT VERIFIED` candidates are omitted. Keep
`INCONCLUSIVE` candidates in a local uncertainty section; never frame them as warnings or inline
pull-request findings. Category and severity are independent of the evidence verdict.

### 4. Report

Group the report by structural concern when that helps comprehension, then order findings by
severity: critical, high, medium, low. Every finding must remain in changed scope and follow this
contract:

> **Found** — verified changed `file:line` structure and evidence.
> **Consequence** — the concrete behavior, operational risk, or comprehension cost it causes.
> **Suggested** — the smallest credible remedy or explicit decision.

```text
## Maintainability review — <target> against <base>

Read-only: yes. Changed scope: <range and paths>. <n> verified finding(s).

### Boundary ownership
### [medium] improvement — src/orders/http.ts:48
**Found** — The changed route duplicates the authorization rule already owned by
`src/orders/policy.ts:19`, with different role handling.
**Consequence** — A later policy change can authorize the same order differently by entry point.
**Suggested** — Route both entry points through the policy function and keep role interpretation
there.

### Local uncertainty
- M-03 — INCONCLUSIVE — <claim>; confound: <missing decisive evidence>.
```

If there are no verified findings, say so in one line. Do not manufacture feedback to justify the
explicit invocation.

## Manual evaluation cases

- A 1,200-line changed file has a cohesive state machine, documented ownership, and a focused test
  suite. Treat size as an investigation trigger; without a concrete structural consequence, record
  no finding.
- A smaller changed handler writes a record, then can fail before updating the corresponding index.
  Trace the failure path, mark the partial-state claim `VERIFIED`, and report atomicity with the
  smallest credible transaction or compensation remedy.
- A suspected extra wrapper has a caller that supplies a meaningful capability boundary. Mark the
  simplification claim `NOT VERIFIED` and drop it.
- A required runtime trace is unavailable. Mark the claim `INCONCLUSIVE`, name the confound, and
  retain it only under local uncertainty.

## Constraints

- Never run without `--lenses maintainability|all` during lifecycle review or a direct standalone request.
- Strictly read-only; do not propose or execute mutations as part of this review.
- Findings target changed lines only; surrounding code is context, not a target.
- Every finding is evidence-backed, names a concrete consequence, and offers a credible remedy.
- No automatic file-size blocker and no generic polish, style, naming, or formatting findings.

## Success criteria

- The report states the changed scope and read-only result.
- Each material claim has a `VERIFIED`, `NOT VERIFIED`, or `INCONCLUSIVE` verdict and matching
  `report`, `drop`, or `local-uncertainty` disposition.
- Every reported finding is changed-scope, structural, evidence-backed, consequential, and
  actionable.
