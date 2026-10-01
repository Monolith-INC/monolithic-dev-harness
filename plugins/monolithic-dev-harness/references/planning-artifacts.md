# Planning Artifacts

Shared contract for the harness's pre-backlog planning skills. These skills help a user decide what
to build before work items or implementation artifacts are created.

## Smallest useful path

Planning is demand-driven, not a mandatory waterfall. Start from the gap in the current intent:

| Missing from the intent | Use |
| --- | --- |
| Options worth considering | `brainstorm-ideas` |
| Confidence that a held idea survives scrutiny | `forge-idea` |
| Current evidence for a decision | `research-decision` |
| A concise product narrative | `product-brief` |
| Agreement across people, teams, or multiple epics | `product-requirements` |
| Shared interaction and visual decisions | `experience-design` |
| Cross-unit technical invariants | `architecture-spine` |
| A short contract ready for backlog decomposition | `product-spec` |

Skip any skill whose question is already answered. An obvious, low-risk change may enter the
existing backlog or build flow directly.

## Defined intent

An intent is ready for `product-spec` when it says:

- why the outcome matters;
- what must be possible when it is done;
- what constraints bend the solution;
- what is explicitly outside the work; and
- what observable result will count as success.

If those answers are absent, use the smallest upstream skill that can establish them. `product-spec`
distills intent; it does not invent product strategy.

## Workspace

Resolve `artifacts_path` from `.harness/settings.json` as described in `project-config.md`. If it is
unset, enter guided bootstrap, ask where planning artifacts should live, show the complete settings
proposal, and apply that reviewed choice through the controlled setup command. Do not ask the user
to edit JSON.

When the user wants persistent output, use:

```text
<artifacts_path>/Planning/<initiative>/
|-- idea/
|-- research/
|-- brief/
|-- requirements/
|-- ux/
|-- architecture/
`-- specs/<epic-or-outcome>/
```

Use the shortest stable kebab-case initiative name the user recognizes. Loose work may omit the
initiative directory only when the user chooses that placement. Planning skills may create their
own subfolder after the destination is known; they never create tracker items, branches, commits, or
pull requests.

## Decision memory

Each persistent planning folder owns a `.decision-log.md`. It is append-only and chronological.
Record one concise entry per accepted decision, constraint, assumption, open question, reversal, or
terminal event. Include the reason when it changes downstream interpretation.

The user-facing artifact is distilled from this log plus cited sources. On update, append the new
decision and re-render the owned artifact; do not erase prior decisions or silently patch around a
conflict. Stable identifiers (`FR-N`, `CAP-N`, `AD-N`) are never renumbered or reused.

The owning skill is the only writer of its artifact. Other skills may cite or adopt it as a
companion, but must not edit it.

## Final idea challenge

Before a product contract is accepted, `product-spec` owns a short `CRITIQUE.md` companion in the
same spec folder. It names the strongest counterargument, unsupported assumptions, plausible
failure cases, and a simpler alternative. `forge-idea` can provide the analysis, but its separate
artifact is optional. Record the user's defense, revision, or decision to abandon in the spec's
decision log; update the product contract when the challenge changes it. Show the contract and
critique together at one review point, not as a new chain of confirmations.

## Create, update, validate

Planning artifact skills support three intents:

- **Create** — establish the workspace, capture decisions, and produce the artifact.
- **Update** — read the artifact and decision log, surface conflicts, append the accepted change,
  and re-render while preserving stable IDs.
- **Validate** — critique without editing, cite specific sections, and offer an update afterward.

In an interactive create, default to a coaching path: elicit the user's decisions, show meaningful
trade-offs, and ask one focused question at a time. Use a fast path when the user asks for speed:
draft the whole artifact, label unsupported inferences `[ASSUMPTION]`, and present them for review.

## Source handling

Read existing project material before asking the user to repeat it. For brownfield architecture and
UX, the repository is evidence; a label or summary is not. For current market, library, platform,
legal, security, accessibility, or standards claims, use current authoritative sources and cite
them. Separate verified facts, user decisions, assumptions, and open questions.

Large source sets are reduced to relevance-filtered notes before synthesis. The canonical product
contract should remain compact enough to read in one pass; expansive tables, diagrams, glossaries,
and owned UX or architecture documents remain companions rather than being copied into it.

## Handoff into delivery

`product-spec` is the bridge into the existing harness:

1. `generate-work-item` or `decompose-backlog` turns its `CAP-N` capabilities into Epic, Feature,
   and Story scope. Every created item records the capability IDs it covers.
2. `generate-breakdown-work-items` turns approved Story acceptance criteria into Tasks; it does not
   reinterpret the product contract.
3. `write-spec` owns the Story's technical *how*. It reads the product spec and its adopted UX and
   architecture companions, treating their stable decisions as constraints.
4. Task-level `architect` sketches code shapes within those constraints. It cannot override an
   `AD-N`; conflicts return to `architecture-spine` or `product-spec` for an explicit update.

The existing approval model is unchanged. Local planning drafts are reversible work products.
Tracker and SCM writes still require the normal complete preview and explicit approval.
