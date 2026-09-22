---
name: review-typescript
description: TypeScript quality lens for changed .ts and .tsx code: runtime boundaries, honest types, exhaustive states, and observable failures. Runs automatically in lifecycle reviews when the repository is TypeScript or the diff includes TypeScript files; also invokable standalone or via --lenses on lifecycle skills.
---

# Review TypeScript

Use this skill for TypeScript review. The agent may invoke it during lifecycle reviews when triggered by configuration, changed `.ts`/`.tsx` scope, or `--lenses` flags, or run it standalone. It is a strictly
read-only quality lens: it changes no source, working-tree file, Git object, index, remote, pull
request, comment, tracker record, or persisted review state. Reading the project knowledge store is
not a mutation and is permitted; its write operations are not.

It reviews changed `.ts` and `.tsx` code only. When embedded in a lifecycle review, merge only `VERIFIED` findings into the parent report lens subsection. Standalone runs produce a full TypeScript review report. It does not create generic polish findings. Read unchanged
types, schemas, callers, tests, and runtime boundaries only when they are necessary evidence for a
claim about the changed scope.

## Project knowledge

When `.monolithic-code-review/sources.json` records a `knowledge.root`, two units inform this lens.
Follow the cost ladder — routing table, then search, then one unit — and never read the whole store.

- `3-mechanics/stack` — compiler strictness, schema authority, runtime and framework versions. Use
  it freely; it saves re-deriving from `tsconfig.json` on every run, and it tells you which
  strictness a claim can already assume.
- `4-rules/coding-standards` — cite a mandated or prohibited pattern **only** when that unit's
  `provenance` is `stated`, meaning a human authored the rule. A `derived` or `assumed` pattern is
  an observation about existing code, not a standard, and reporting one is exactly the
  rubric-copying this lens forbids.

A store entry never substitutes for evidence. The finding threshold is unchanged: the changed code
must actually accept an invalid runtime value, make an unsound type claim, lose a reachable state,
hide an outcome, or prevent useful diagnosis. Project knowledge tells you what the project expects;
it does not tell you the code is wrong.

## Procedure

### 1. Establish the TypeScript boundary without mutation

Ask for the base and target when they are ambiguous. Use read-only evidence:

```bash
git status --short
git diff --stat <base>...<target> -- '*.ts' '*.tsx'
git diff <base>...<target> -- '*.ts' '*.tsx'
```

Read each changed TypeScript file in full and inspect its immediate runtime inputs, schema or
parser, public types, callers, and relevant tests. Pre-existing modified or untracked paths are
user-owned; never clean, stage, stash, or alter them.

### 2. Test actual type and runtime invariants

Inspect only claims relevant to changed scope:

| Concern | Check |
| --- | --- |
| Discriminated states | State variants have a stable discriminator and changed consumers branch on it rather than infer state from optional fields. |
| External-data parsing | `unknown` data from network, storage, environment, events, or third parties is parsed or validated before domain use. |
| Honest narrowing | Guards, assertions, and casts follow evidence that establishes the narrowed property; an assertion cannot replace validation. |
| Schema derivation | Where a schema is the runtime authority, types are derived from it or equivalence is demonstrated so the two cannot drift unnoticed. |
| Exhaustiveness | Changed discriminated unions have an exhaustive consumer or an explicit failure path for unhandled variants. |
| Total signatures | Changed functions state all meaningful success, absence, and failure outcomes instead of returning an undocumented sentinel, `undefined`, or throw path. |
| Structured telemetry | Changed error/operational telemetry preserves queryable fields such as event name, error kind, operation, and safe correlation context rather than only prose. |

Do not repeat a rule because a rubric says so. A finding requires evidence that the actual changed
code accepts an invalid runtime value, makes an unsound type claim, loses a reachable state, hides
an outcome, or prevents useful operational diagnosis.

**Representation is not an invariant by itself.** A property typed `number` does not enforce a
non-negative duration, valid range, unit, or relationship to another field. Do not claim that this
type alone makes invalid ranges unconstructable:

```ts
type Interval = { start: number; durationMs: number };
const invalid: Interval = { start: 100, durationMs: -1 };
```

The negative-duration counterexample rejects the unsound claim. A cast is valid only after full
runtime validation establishes the invariant, for example:

```ts
type NonNegativeDurationMs = number & { readonly __brand: "NonNegativeDurationMs" };

function parseDurationMs(value: unknown): NonNegativeDurationMs | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return undefined;
  return value as NonNegativeDurationMs;
}
```

The cast is justified here because the parser proves number-ness, finiteness, and non-negativity
before constructing the branded value. If changed code lacks comparable proof, do not accept a
cast merely because its target type looks semantic.

### 3. Record evidence and decide disposition

For every material candidate, create an evidence record with: `id`, falsifiable `claim`, expected
runtime or type invariant, decisive `evidence`, and, where applicable, comparable `baseline` and
`treatment`; record `confounds` for unavailable runtime, generated schema, or test evidence.

| Verdict | Meaning | Disposition |
| --- | --- | --- |
| `VERIFIED` | Evidence supports the claim and its stated invariant. | `report` |
| `NOT VERIFIED` | Evidence contradicts the claim or proves the invariant holds. | `drop` |
| `INCONCLUSIVE` | Missing or invalid boundary, runtime, or schema evidence prevents a decision. | `local-uncertainty` |

Only `VERIFIED` candidates become findings. `NOT VERIFIED` candidates are omitted. Keep
`INCONCLUSIVE` candidates local; they are never warnings or inline pull-request findings. Category
and severity remain independent of verdict.

### 4. Report

Group findings by type or boundary concern when useful; otherwise use severity order: critical,
high, medium, low. Every finding must be in changed scope and follow:

> **Found** — verified changed `file:line` type/boundary behavior and evidence.
> **Consequence** — the concrete invalid state, runtime failure, contract drift, or diagnostic loss.
> **Suggested** — the smallest credible parser, type, exhaustive branch, signature, or telemetry remedy.

```text
## TypeScript review — <target> against <base>

Read-only: yes. Changed TypeScript scope: <paths>. <n> verified finding(s).

### External-data parsing
### [high] error — src/events/decode.ts:31
**Found** — The changed event handler casts `payload as Event` before checking its discriminator
or fields.
**Consequence** — A malformed producer payload reaches domain handling and can select an invalid
state branch at runtime.
**Suggested** — Parse `unknown` at the boundary, then pass only the validated discriminated union
to domain code.

### Local uncertainty
- T-04 — INCONCLUSIVE — <claim>; confound: <missing decisive evidence>.
```

If there are no verified findings, say so in one line rather than inventing feedback.

## Manual evaluation cases

- A changed HTTP decoder accepts `unknown`, validates every union variant, and returns a derived
  domain type. Mark a suspected cast finding `NOT VERIFIED` and drop it.
- A changed state switch omits a newly added discriminator variant. Trace the reachable variant,
  mark the exhaustiveness claim `VERIFIED`, and report the concrete unhandled outcome.
- A review claim says `{ durationMs: number }` prevents negative durations. Construct
  `{ start: 100, durationMs: -1 }`, mark that claim `NOT VERIFIED`, and do not report it as a
  safety guarantee. Accept a branded-duration cast only after full parsing validates type,
  finiteness, and non-negativity.
- A provider schema cannot be retrieved and no fixture establishes its shape. Mark any schema-drift
  claim `INCONCLUSIVE` with that confound; list it only under local uncertainty.

## Constraints

- Lifecycle reviews invoke this lens only when `quality_lenses.typescript` is `mandatory`, the
  changed scope includes `.ts` or `.tsx`, or the user passes `--lenses typescript` or
  `--lenses all`. It remains available as a standalone explicit invocation; never run it for an
  unrelated non-TypeScript lifecycle review by implication.
- Strictly read-only; do not modify code, files, Git state, remotes, pull requests, comments, or
  tracker records.
- Findings target changed `.ts` or `.tsx` lines only; surrounding code supplies evidence only.
- Numeric representation alone never proves a range or relational invariant.
- Every finding is evidence-backed, names a concrete consequence, and offers a credible remedy.
- No generic stylistic, naming, formatting, or rubric-copying findings.

## Success criteria

- The report states the changed TypeScript scope and read-only result.
- Every material claim receives `VERIFIED`, `NOT VERIFIED`, or `INCONCLUSIVE` with the matching
  `report`, `drop`, or `local-uncertainty` disposition.
- Reported findings are changed-scope, evidence-backed, consequential, and actionable.
- The negative-duration counterexample rejects the unsound representation claim, while the valid
  cast example requires full validation first.
