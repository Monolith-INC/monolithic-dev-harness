---
name: review-story-preflight
description: Use when a user story is finished but before pushing the last commits or opening a pull request, to check the whole story branch against the story description, requirements and definition of done. Optional flags: --lenses maintainability|typescript|all.
---

# Review Story — Pre-flight

The gate between "the work is done" and "the work becomes a pull request". This reviews the
**entire story branch**, not a single task, against the story's own description, requirements, and
definition of done. Nothing is pushed and nothing is posted — findings go to the user, who decides
what to fix before the PR exists.

Requires `.monolithic-code-review/sources.json`. If it is missing, run `review-setup` first.
## Review flags and quality lenses

User-invoked lifecycle reviews accept optional flags in the request:

| Flag | Effect |
| --- | --- |
| `--lenses maintainability` | Run the maintainability lens on the changed scope before reporting. |
| `--lenses typescript` | Force the TypeScript lens even when it would not otherwise trigger. |
| `--lenses all` | Run both maintainability and TypeScript lenses. |

Parse these flags from the user's message. Maintainability never runs without an explicit flag.
TypeScript runs when mandatory by configuration, when the changed scope includes `.ts` or `.tsx`
files, or when forced by flag.

Read `quality_lenses` from `.monolithic-code-review/sources.json` when present. After
`review-setup`, TypeScript repositories record `quality_lenses.typescript: "mandatory"`.

| Lens | Runs when |
| --- | --- |
| **TypeScript** | `quality_lenses.typescript` is `mandatory`, **or** the changed scope includes any `.ts`/`.tsx` file, **or** the user passed `--lenses typescript` or `--lenses all`. |
| **Maintainability** | The user passed `--lenses maintainability` or `--lenses all` only. |

When a lens triggers, execute the full read-only procedure from the matching skill
(`review-typescript` or `review-maintainability`) on the **same changed scope** as this review.
Merge only `VERIFIED` lens findings into this report under `### Quality lens — TypeScript` or
`### Quality lens — Maintainability`. Use the same evidence verdicts. Do not duplicate a defect
already reported in the requirements section — keep the requirements finding and omit the lens copy.

Complete requirements-first analysis before lens passes unless a lens check is the smallest decisive
evidence for a requirement claim.

## Project knowledge

Requirements say what this work should do. The **project knowledge store** says what this repository
already requires of any change — its architecture and dependency rules, its conventions, its real
build and test commands, which paths are generated. Read it, and a divergence from how this codebase
works becomes a citable finding instead of an opinion.

Read `knowledge.root` from `.monolithic-code-review/sources.json`. When it is absent or `null`, say
so once and review without it. A missing store is never a reason to substitute your own idea of what
this project's standards are — that is the same failure as inventing a requirement.

Retrieval is a cost ladder. Follow it in order and stop as soon as the question is answered:

| Step | With the knowledge MCP adapter | Without it | Returns |
| --- | --- | --- | --- |
| 1 | `knowledge_catalog` | Read `<root>/catalog.tsv` | Routing table — `read_when` and facets, never content |
| 2 | `knowledge_find` | Grep the tree under `<root>` | Locations with matched terms and a snippet |
| 3 | `knowledge_fetch` | Read one unit or one heading | One unit, with its version token |

Never read the whole store. Cache the routing table for the run rather than re-reading it.

**Project knowledge is evidence, not a finding generator.** A unit raises a finding only when both
hold:

1. The unit's `provenance` is `derived` or `stated` — a fact read out of the tree, or one a human
   authored. A `provenance: assumed` unit is `INCONCLUSIVE` by construction and stays in local
   uncertainty.
2. The changed lines actually contradict it. A change that merely differs from an unrelated unit is
   not a finding.

Cite the unit `id` in the finding exactly as a `gap` cites its definition-of-done line. A reader must
be able to check the claim without asking you what you meant.

When the store and the code disagree and the code is right, that is **store drift**: report it under
local uncertainty naming the unit, so the store gets corrected. Do not hold a diff to a documented
rule the team has already moved past.


## Why this is not `review-task` on a bigger diff

A story is complete in a way individual tasks are not. Three checks only make sense at this level:

1. **Coherence across tasks.** Task 3 may have quietly undone what task 1 established. Only the
   whole-branch diff shows it.
2. **The definition of done as a whole.** Individual tasks can each pass while the story's DoD
   still fails — most often documentation, migrations, or observability nobody's task owned.
3. **Readiness to be reviewed by a human.** Debug statements, commented-out code, `TODO`s added
   during the work, and commits that will confuse a reviewer.

## Procedure

### 1. Establish what the story asked for

Resolve the story through `fetch_work_item`. Also call `fetch_parent` to get the feature it belongs
to — a story can satisfy its own text while contradicting its parent's intent, and that is worth
knowing before a human reviewer finds it.

Extract goal, requirements, DoD, and out-of-scope statements. If `fetch_work_item` is unsupported,
ask the user for the story text rather than inferring it.

### 2. Establish the whole-branch diff

```bash
git branch --show-current
git fetch origin
BASE=$(git merge-base HEAD origin/<base-branch>)
git diff --stat $BASE...HEAD
git diff $BASE...HEAD
git log --oneline $BASE..HEAD
```

Determine the base branch from the story's parent feature branch when the workflow stacks branches,
otherwise from the repository default. Confirm the base with the user if it is ambiguous — diffing
against the wrong base produces a review of unrelated work.

Read changed files in full, plus their immediate callers and callees.

### 3. Review

Apply the same categories and severities as `review-task`:

| Category        | What it means                                                                          |
| --------------- | -------------------------------------------------------------------------------------- |
| **error**       | The change is wrong: a bug, a broken contract, a regression                              |
| **gap**         | A requirement or DoD item is unmet or only partly met                                   |
| **improvement** | A pertinent improvement, tied to this story's goal                                       |
| **off-scope**   | Work no requirement asked for, including anything the story excluded                     |

Severities are **critical**, **high**, **medium**, **low**, as in `review-task`.

Then run the pre-flight checks that are specific to this gate:

- **Cross-task contradictions** — a later commit reverting or bypassing an earlier one.
- **Parent-feature agreement** — does this story move its feature toward its stated goal?
- **Leftovers** — debug logging, commented-out blocks, `TODO`/`FIXME` added by this branch,
  temporary fixtures, credentials or endpoints pointing at development environments.
- **Commit legibility** — commits a reviewer can follow. Say so if the history would be materially
  clearer squashed or reordered; do not rewrite it yourself.
- **Verification evidence** — do tests, migrations, or docs the DoD requires actually exist in the
  diff? Run the project's test command and report the real result — `3-mechanics/testing` in the
  knowledge store names it when a store exists; otherwise discover it, and say which you used.

### 4. Build an attention-ordered change map when it earns its place

Before detailed findings, add a change map only when the diff has multiple responsibilities or
significant review noise: for example, it crosses core behavior and wiring, spans several layers
whose relationship affects correctness, or generated/mechanical churn could hide a material change.
Do not produce one for a single-responsibility, easy-to-follow diff merely because it touches
multiple files.

Order the map by reviewer attention, not diff order:

1. **Core behavior** — algorithms, state transitions, domain rules, public contracts, and the
   tests that establish them. Name the reviewer entry point and the cross-file relationship it
   relies on.
2. **Wiring and integration** — routes, dependency wiring, configuration, adapters, and their
   relationship to the core behavior they invoke.
3. **Mechanical or generated** — formatting, renames, imports, generated files, and re-exports.
   List paths and statistics unless a concrete risk needs more context. Never call this group safe;
   it still needs proportionate review.

Use only the aid that removes a real comprehension barrier: pseudocode when syntax or nesting hides
the essential algorithm; a concrete before/after trace when the observable outcome is hard to
predict; and a labeled **Risk callout** only for a subtle, breaking, concurrent, security, or
performance-sensitive point. The map is an orientation aid, not a second diff or a finding list.


### Quality lens pass (when triggered)

After establishing the changed scope and before the final report, run each triggered quality lens
(see **Review flags and quality lenses** above). Requirements-first findings stay in their section;
lens-only `VERIFIED` findings go under the lens subsection.

### 5. Record evidence before reporting

For every material criterion verdict or candidate discrepancy, create an evidence record with an
`id`, falsifiable `claim`, `expected` requirement or invariant, decisive `evidence`, and, where a
comparison is made, the same-measure `baseline` and `treatment`; record `confounds` when present.

| Verdict | Meaning | Disposition |
| --- | --- | --- |
| `VERIFIED` | Evidence supports the claim and meets its stated threshold. | `report` |
| `NOT VERIFIED` | Evidence contradicts the claim or misses its stated threshold. | `drop` |
| `INCONCLUSIVE` | Missing or invalid access, baseline, measurement, or environment prevents a decision. | `local-uncertainty` |

Category and severity remain separate from evidence verdict. Only `VERIFIED` discrepancies become
findings. Keep `INCONCLUSIVE` records in a local uncertainty section, never as findings or softened
warnings.

### 6. Report

Same three-part contract:

> **Found** — what is there, with `file:line`
> **Consequence** — what it costs or breaks, concretely
> **Suggested** — the specific action to take

```text
## Story pre-flight — <story id>: <title>

Branch <head> vs <base>, <n> commits, <m> files.
Requirements: <x> satisfied, <y> partial, <z> unmet. DoD: <a>/<b> met.

VERDICT: ready for pull request | blocked by <n> finding(s)

### Change map
- **Core behavior** — `<entry path:line>` — reviewer entry point: <where to start>.
  Relationship: `<caller>` → `<domain rule>` → `<observable result>`.
- **Wiring and integration** — `<path>` — connects <dependency or route> to <core entry point>.
- **Mechanical or generated** — `<paths and statistics>` — <why it is present and any review risk>.

Include this section only when the trigger above is met. Omit empty groups and any unneeded
pseudocode, trace, or risk callout.

### Findings (severity order: critical, high, medium, low)
### [high] gap — no migration for the new column
**Found** — `orders.status` is read in src/orders/repo.ts:88 but no migration adds it.
**Consequence** — Deploy fails on any environment whose schema predates this branch.
**Suggested** — Add the migration to db/migrations/ and note it in the story's DoD checklist.
```

End with an explicit verdict line. "Ready for pull request" means every DoD item is met and no
critical or high finding is open. Anything less is blocked, and the report says by what.

Close with criteria **not verifiable from the diff**.

## Manual evaluation cases

- Supported claim: a branch reads a new database column while its full migration set contains no
  migration adding it; cite both, mark `VERIFIED`, and report the `gap` finding.
- Disproved claim: a suspected cross-task regression is contradicted by the current caller and the
  branch test covering the earlier behavior; mark `NOT VERIFIED` and drop it.
- Inaccessible evidence: the DoD requires a CI-only deployment proof that cannot be accessed from
  the branch; mark `INCONCLUSIVE` with unavailable CI evidence as a confound and keep it local.
- Multi-layer fixture: a new domain validation rule, its HTTP route wiring, and a regenerated client
  each change. Produce core → wiring → mechanical groups, name the route-to-rule relationship, and
  flag a stale generated contract only if evidence supports it; do not call the generated output
  safe merely because it is generated.
- Trivial fixture: one self-contained boundary correction with its focused test. Omit the map,
  pseudocode, before/after trace, and risk callout; report any verified finding in severity order.

## Constraints

- Read-only. Do not push, do not open a pull request, do not amend commits.
- Comment only on changed lines.
- Do not tell the user to "check" or "verify" — determine it, or state it is not verifiable.
- No stylistic nits.
- If the branch is already pushed and a PR exists, this is the wrong skill — use
  `review-story-postflight`.

## Success criteria

- Every requirement and DoD item has an explicit verdict.
- The whole-branch diff was reviewed against the correct base.
- Pre-flight leftovers were checked for explicitly.
- The report ends with a ready/blocked verdict.
