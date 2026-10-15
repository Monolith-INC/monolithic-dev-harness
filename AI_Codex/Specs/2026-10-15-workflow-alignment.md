---
title: Workflow alignment — BMad, agile-backlog-toolkit and codex-workflows in the harness
type: design
status: draft
created: 2026-10-15
owner: monolithic-dev-harness maintainers
---

# Workflow alignment

The harness is assembled from three sources. Each one brings a workflow, not only skills:

| Source | Copied at | Brings | Owns |
| --- | --- | --- | --- |
| BMad Method | `1cbcfa2` | BMad Build discovery and planning, elicitation, review, product skills | Understanding and the approach |
| agile-backlog-toolkit | `e7ae82c` | Work-item creation, enrichment, decomposition, sizing, breakdown, validation | The backlog: Epics, Features, Stories, Tasks, one Implementation Plan per Story |
| codex-workflows-plugin | `75c22f0` | Tracked delivery: start, spec with critic review, PR review, resolution, Feature stacks | Delivery and its evidence |

Today the harness keeps the skills but drops much of the workflow that links them. This document
sets out how the three workflows run end to end inside the harness, and the sequences a user goes
through depending on what they start with. It is a working draft to refine into the alignment plan.

Rendered diagrams: [2026-10-15-workflow-alignment-diagrams/](2026-10-15-workflow-alignment-diagrams/).

## Problem: today's six-stage route

On the six-stage route, the default for feature work, three toolkit skills run in a harness "draft
mode" that skips their own phases and gates, writes a harness-invented `tracker-drafts.json`, and
leaves creation to `harness tracker publish` after the final approval. Work items should instead be
created in the tracker first, by the toolkit's own workflow, before the Story plans and before code.
The draft mode also caused the deadlock in trial `20261015-day001-planning-gate-02`: the plan needs
a linked Story, and the Story exists only after the final approval.

| What | Where (under `plugins/monolithic-dev-harness/`) |
| --- | --- |
| Draft mode replaces each skill's phases and gates with `implementation-confirm` | `skills/generate-work-item/SKILL.md`, `skills/decompose-backlog/SKILL.md`, `skills/generate-breakdown-work-items/SKILL.md`, section "Six-stage preparation mode" |
| Preparation prepares only `generate-work-item` and `bmad-spec` | `config/prepared-workflows.json`, stage `preparation` |
| Publication writes description, acceptance criteria and estimate only; no hours, iteration, Breakdown state, read-back, or id write-back | `scripts/harness/bundle.py` `_create_all`, `_description` |
| The refinement check requires one Task per Story, not Staging/Review/Breakdown; no coverage audit or Definition of Ready | `scripts/harness/bundle.py` `check_drafts` |
| `tracker-drafts.json` in the planning folder counts as code when no source globs are set, so the code-change gate refuses it | `scripts/policy/commands.py` `is_code`; trial 02 parent report, finding 4 |

```mermaid
flowchart TD
    D[Discovery] --> P[Planning] --> H[Hardening]
    H --> PR["Preparation<br/>skills in draft mode, gates skipped"]
    PR --> TD["tracker-drafts.json<br/>harness-invented hierarchy file"]
    TD --> PL[Implementation plan written last]
    PL --> CF{{"implementation-confirm<br/>one approval for everything"}}
    CF --> PUB["harness tracker publish<br/>items created now, without hours,<br/>Breakdown state, or read-back"]
    PUB --> ST["start-ticket: link the Story,<br/>move it to in progress"]
    ST --> EX[Execution]
```

Where trial 02 stalled:

```mermaid
flowchart LR
    W["Write tracker-drafts.json<br/>(planning folder, JSON)"] --> GATE{"code-change gate:<br/>work item linked?"}
    GATE -- "no Story yet" --> X[Refused]
    LINK["Link the Story"] --> NEED["needs a Story key"]
    NEED --> PUBL["Story exists only after<br/>harness tracker publish"]
    PUBL --> CONF["publish needs the approved bundle"]
    CONF --> W
```

## Principles

1. Each source's workflow runs as written: its phases, gates, read-backs, audits and critic reviews.
   The harness adds no parallel mechanics for what a source already owns.
2. Tracker first. Work items exist in the selected tracker, read back, before the Story plans are
   approved and before code changes.
3. Every tracker write goes through the harness gateway and its approval windows; every human
   decision goes through `harness decision present`.
4. What each stage needs and produces is declared in `config/prepared-workflows.json`. Nothing in the
   harness's own decisions depends on version control; Git-specific steps run only with Git delivery.
5. Every document or work item that is created is shown to the user for approval, then saved through
   the selected tracker. There is no later approval that bundles several of them.
6. Work items are the source of truth. Plans, specs and Tasks are derived from them; a change of
   direction updates the work items first, then what derives from them.

## The whole route

```mermaid
flowchart TD
    REQ[User request, idea, or work item] --> BEGIN["harness begin<br/>setup, work session, saved request"]
    BEGIN --> ROUTE{What did the user bring?}
    ROUTE -- "an idea to shape" --> IDEA["BMad product skills<br/>brainstorm, forge, research,<br/>brief, bmad-spec, product spec"]
    IDEA --> GO{"Continue into<br/>technical discovery?"}
    GO -- "yes" --> DISC
    GO -- "no" --> STOP["Stop with the brief or spec"]
    ROUTE -- "a request, draft, or work item" --> DISC
    ROUTE -- "an already-refined Story" --> ASK{"Run the BMad<br/>front half first?"}
    ASK -- "yes" --> DISC
    ASK -- "no" --> EXE

    subgraph BMAD["BMad: the approach"]
        DISC["Discovery<br/>bmad-build step 1: clarify and route"] --> PLAN["Planning<br/>bmad-build step 2: approach draft<br/>bmad-advanced-elicitation methods"]
        PLAN --> HARD["Hardening<br/>bmad-review at the chosen depth"]
    end

    subgraph ABT["agile-backlog-toolkit: the backlog"]
        HARD --> REF["Refinement<br/>check format, enrich what fails<br/>(amend existing items when the approach changed them),<br/>decompose, size, create, read back, audit"]
        REF --> BRK["Breakdown per Story<br/>Implementation Plan approved<br/>(= implementation-confirm),<br/>Tasks + Staging/Review/Breakdown approved, hours"]
        BRK --> VAL["validate-artifact on what was created"]
    end

    subgraph HAR["harness: the contract"]
        VAL --> PREP["Preparation<br/>risk, verification, manifest<br/>(each approved when created)"]
    end

    subgraph CW["codex-workflows: delivery"]
        PREP --> EXE["Execution per Story<br/>start-ticket, write-spec for missing<br/>technical specs, implement-story"]
        EXE --> VER["Verify<br/>review, review-pr, resolve-ticket"]
        VER --> FEAT["Feature close<br/>stack merge and finish (Git delivery),<br/>or finish-feature-development local mode"]
    end
```

## Front half: BMad

| Stage | BMad skill | Produces |
| --- | --- | --- |
| Discovery | `bmad-build` step 1 (rendered by `harness begin` into `_bmad/render/`) | Clarified request, route, initiative choice, code map |
| Planning | `bmad-build` step 2, `bmad-advanced-elicitation` | The approach draft and its memlog; depth and method choices |
| Hardening | `bmad-review` | Triaged findings; consequential choices settled |
| Idea route | `brainstorm-ideas`, `forge-idea`, `research-decision`, `product-brief`, `bmad-spec`, `product-spec`, `plan-initiative` | A shaped idea and its product spec; the user then chooses to continue into technical discovery or stop |
| Any stage, as needed | `bmad-correct-course`, `bmad-project-context`, `bmad-deep-recon`, `bmad-qa-generate-e2e-tests` | Change of direction, instruction drift, reconnaissance, end-to-end tests |

BMad's approach draft is the input to refinement. It is carried as a reviewed companion, not
approved as a plan: the execution contract is each Story's Implementation Plan. `bmad-spec` writes
the product-level spec (why, capabilities, constraints, non-goals, success signal) on the idea route;
it no longer writes companions in preparation, where they overlapped with `write-spec`.

## Middle: the backlog (agile-backlog-toolkit)

```mermaid
flowchart TD
    IN[Input from Hardening] --> CHG{"Did the approach change<br/>existing items?"}
    CHG -- "yes, Epic or Feature tree" --> AMD["amend-workitems<br/>backup, one change set approved,<br/>plan updated before Tasks, hours recomputed"]
    CHG -- "yes, one Story" --> ENR["enrich-work-item, approved,<br/>then breakdown rules for plan and Tasks"]
    AMD --> FMT
    ENR --> FMT
    CHG -- "no" --> FMT{"Already a formatted item?<br/>validate-artifact"}
    FMT -- "passes" --> KEEP[Keep as is]
    FMT -- "fails, or raw text" --> GWI["generate-work-item<br/>or enrich-work-item"]
    GWI --> G0{{"Approve draft<br/>(publish-items)"}}
    G0 --> C0[Create, read back, write id into draft]
    KEEP --> LVL{Level}
    C0 --> LVL
    LVL -- Epic --> EF{"Child Features?"}
    EF -- "none or ask" --> MKF["decompose-backlog: create<br/>intervening Features (ask first)"]
    EF -- "existing" --> FS
    MKF --> FS
    LVL -- Feature --> FS{"Child Stories<br/>formatted?"}
    FS -- "yes" --> CHK[validate each Story]
    FS -- "no" --> DEC["decompose-backlog<br/>Gate 1 split, Gate 2 bodies,<br/>create, read back, audit"]
    LVL -- "User Story" --> SZ
    CHK --> SZ
    DEC --> SZ{"Over the point<br/>ceiling?"}
    SZ -- yes --> SPL["split-story or a Spike"] --> SZ
    SZ -- no --> BRK["generate-breakdown-work-items per Story<br/>Implementation Plan saved first"]
    BRK --> GP{{"Approve the plan<br/>(implementation-confirm, pins the note)"}}
    GP --> TSK["Propose Tasks + Staging/Review/Breakdown,<br/>hours capped at capacity"]
    TSK --> G3{{"Approve Tasks<br/>(publish-items)"}}
    G3 --> C2["Create Tasks, read back,<br/>Breakdown Done + receipt"]
```

## Back half: delivery (codex-workflows)

```mermaid
flowchart TD
    CONF["Story plan approved, Tasks created,<br/>preparation documents approved"] --> NEXT[Next Story in order]
    NEXT --> ST["start-ticket<br/>link the work session, move to in progress<br/>(Git delivery: check out the key branch)"]
    ST --> SP{"Technical spec kinds still missing?<br/>tech-spec, design doc, ADR, API contract"}
    SP -- yes --> WS["write-spec<br/>draft, Actor-Critic review (max 3),<br/>user approves, publish versioned artifact"]
    SP -- no --> IMP
    WS --> SCOPE{"Spec changes the<br/>Story's scope?"}
    SCOPE -- yes --> AMEND["Back to refinement:<br/>amend the work items, then plan and Tasks"]
    SCOPE -- no --> IMP["implement-story, per Task<br/>architect, failing test, implement,<br/>check, deslop, commit (Git delivery)"]
    IMP --> TD["Task done<br/>(its Story's session)"]
    TD --> MORE{More Tasks?}
    MORE -- yes --> IMP
    MORE -- no --> REV["review stage<br/>requirements check, thermos,<br/>ready verdict"]
    REV --> PR{Git delivery?}
    PR -- yes --> BPR["branch-and-pr: draft PR<br/>review-pr: comply / defer / reject"]
    PR -- no --> RES
    BPR --> RES["resolve-ticket<br/>resolution report with Actor-Critic,<br/>verification evidence"]
    RES --> DONE["Story done<br/>(completion requirements)"]
    DONE --> LEFT{More Stories?}
    LEFT -- yes --> NEXT
    LEFT -- no --> FC{"Feature with several Stories<br/>and Git delivery?"}
    FC -- yes --> STACK["reconcile-feature-stack,<br/>merge-story-stack-into-feature,<br/>finish-feature-development"]
    FC -- no --> FIN["finish-feature-development, local mode<br/>every Story done, closing evidence,<br/>approval, Feature done"]
```

## Sequences by starting point

Every sequence starts with `harness begin`, which checks setup, routes the work session and saves
the exact request. The work session tracks the item the user starts with: an Epic, a Feature or a
Story (an idea or draft is tracked by the item refinement creates for it). The four starting points
differ in what refinement has to do.

### 1. An idea or a free-text draft

```mermaid
sequenceDiagram
    actor U as User
    participant H as Harness
    participant B as BMad
    participant K as Backlog toolkit
    participant T as Tracker

    U->>H: idea or draft text
    H->>U: What would you like to do? (investigate, draft items, explore)
    alt explore the idea
        H->>B: product skills (brainstorm, forge, research, brief, bmad-spec)
        B-->>U: shaped idea, product brief or spec
        H->>U: continue into technical discovery, or stop here?
    end
    H->>B: Discovery (clarify and route)
    B->>U: standalone or initiative?
    H->>U: planning depth, methods
    B-->>H: approach draft, hardened
    H->>K: refinement from the approach
    K->>U: what level is this? (Epic, Feature, Story)
    K->>U: Gate 1: approve the split
    K->>U: publish-items: create the items
    K->>T: create Epic/Feature/Stories, read back
    loop each Story
        K->>U: approve the plan (implementation-confirm)
        K->>U: publish-items: create the Tasks
        K->>T: create Tasks, Breakdown Done
    end
    Note over H,T: delivery runs per Story
```

### 2. An Epic

```mermaid
sequenceDiagram
    actor U as User
    participant H as Harness
    participant B as BMad
    participant K as Backlog toolkit
    participant T as Tracker

    U->>H: Epic (tracker key or document)
    H->>B: Discovery reads the Epic verbatim
    B-->>H: approach, hardened
    H->>K: validate-artifact on the Epic
    alt format fails
        K->>U: enrich-work-item, approve body
        K->>T: update the Epic, read back
    end
    alt Epic has no Features
        K->>U: create intervening Features or target existing ones?
        K->>U: approve the Features
        K->>T: create Features, read back
    end
    loop each Feature
        K->>U: Gate 1 split, Gate 2 bodies
        K->>T: create Stories, read back, audit coverage
    end
    loop each Story (fan-out)
        K->>U: approve the plan (implementation-confirm)
        K->>U: approve Tasks and hours
        K->>T: create Tasks, Breakdown Done
    end
    Note over H,T: delivery runs Story by Story, then each Feature closes, then the Epic
```

### 3. A Feature

```mermaid
sequenceDiagram
    actor U as User
    participant H as Harness
    participant B as BMad
    participant K as Backlog toolkit
    participant T as Tracker

    U->>H: Feature (tracker key or document)
    H->>B: Discovery reads the Feature and its Stories
    B-->>H: approach, hardened
    H->>K: validate the Feature and each child Story
    alt Feature or Stories fail the format
        K->>U: enrich what fails, approve bodies
        K->>T: update, read back
    end
    alt no child Stories
        K->>U: Gate 1 split, Gate 2 bodies
        K->>T: create Stories, read back, audit coverage
    end
    loop each Story
        K->>K: split-story when over the ceiling
        K->>U: approve the plan (implementation-confirm)
        K->>U: approve Tasks and hours
        K->>T: create Tasks, Breakdown Done
    end
    Note over H,T: Stories delivered in order, Feature closes via the stack (Git) or locally
```

### 4. A User Story

```mermaid
sequenceDiagram
    actor U as User
    participant H as Harness
    participant B as BMad
    participant K as Backlog toolkit
    participant T as Tracker

    U->>H: User Story (tracker key or document)
    H->>B: Discovery reads the Story and its Feature
    B-->>H: approach, hardened
    H->>K: validate-artifact on the Story
    alt no parent Feature
        K->>U: name the parent Feature (Definition of Ready)
    end
    alt format fails
        K->>U: enrich, approve body
        K->>T: update, read back
    end
    alt over the point ceiling
        K->>U: split-story plan or Spike
        K->>T: create the sub-stories, read back
    end
    alt no Tasks yet
        K->>U: approve the plan (implementation-confirm)
        K->>U: approve Tasks and hours
        K->>T: create Tasks, Breakdown Done
    end
    H->>T: start-ticket: in progress, session linked
    Note over H,T: delivery for this Story
```

### A Story that is already refined

When the Story already has its Tasks in the tracker and an approved Implementation Plan, the harness
asks the user whether to run the BMad front half or go straight to delivery.

- **Straight to delivery:** `start-ticket` links it, which meets the code-change requirements, and
  the `implement-approved-item` route (setup → build → verify) runs.
- **Front half first:** if discovery, planning or hardening changes anything, the work items are
  updated first, as the toolkit does it: `amend-workitems` for an Epic or Feature tree (backup, one
  approved change set, the plan updated before its Tasks, hours recomputed), or `enrich-work-item`
  plus the breakdown rules for a single Story. The updated plan and Tasks are approved again.

## Approval mechanics for one Story

Each toolkit gate is presented with `harness decision present` and bound to the content shown, so a
tracker write is allowed only for what the user approved.

```mermaid
sequenceDiagram
    actor U as User
    participant A as Agent (toolkit skill)
    participant H as Harness (hooks, decisions)
    participant T as Tracker (gateway)

    A->>H: decision present --gate refinement-split
    H->>U: Gate 1: approve the split?
    U->>H: Approve
    A->>H: decision present --gate publish-items (Story bodies)
    U->>H: Approve (bound to the shown bodies)
    A->>T: create Stories, read back
    loop each Story
        A->>H: decision present --gate implementation-confirm (the saved plan)
        U->>H: Approve
        H->>H: pin the plan note (plan_approved holds)
        A->>H: decision present --gate publish-items (Tasks, hours)
        U->>H: Approve
        A->>T: create Tasks, Breakdown Done + receipt
    end
    A->>T: start-ticket: move the Story to in progress
    A->>H: work-session link --work-item STORY
    Note over A,H: code-change requirements now hold
```

What the code-change gate reads (`execution.requires` in `config/prepared-workflows.json`) and where
each requirement comes from:

```mermaid
flowchart LR
    subgraph Catalog["execution.requires"]
        L[work_item_linked]
        TP[tasks_parented]
        PA[plan_approved]
        WS[work_item_started]
    end
    BRKP["Refinement:<br/>generate-breakdown-work-items"] --> TP
    BRKP --> PLN["Story's Implementation Plan note"]
    PLN --> CONF2["implementation-confirm<br/>pins the approved note"] --> PA
    STK["start-ticket"] --> WS
    STK --> L
```

## Approvals per starting point

| Starting point | Split | Create items | Story plan | Create Tasks |
| --- | --- | --- | --- | --- |
| Idea or draft | Gate 1 per decomposed level | 1 `publish-items` per level | 1 `implementation-confirm` per Story | 1 `publish-items` per Story |
| Epic | Gate 1 per Feature | Features, then Stories | 1 `implementation-confirm` per Story | 1 `publish-items` per Story |
| Feature | Gate 1 when Stories are missing | Stories when missing | 1 `implementation-confirm` per Story | 1 `publish-items` per Story |
| User Story | split plan only when oversized | sub-stories only when split | 1 `implementation-confirm` | 1 `publish-items` |

Already formatted items are only validated; updates to existing items need their own approval.
Preparation documents and `write-spec` specs are each approved when created. Closing a Feature
locally takes one approval.

## What changes in the harness

| Area | Change |
| --- | --- |
| Catalog | New `refinement` stage after `hardening` preparing `generate-work-item`, `enrich-work-item`, `amend-workitems`, `decompose-backlog`, `split-story`, `generate-breakdown-work-items`, `validate-artifact`, `auto-fix-artifact` and `generate-plain-language-documentation`, with tracker operations; the `onboarding` route gains the stage. `preparation` keeps risk, verification and the manifest. `execution` prepares `start-ticket`, `write-spec`, `implement-story`; `verify` prepares the review stage, `review-pr` (Git delivery), `resolve-ticket`, and the Feature-close skills. Stack skills are prepared only with Git delivery. |
| Skills | Remove the three "Six-stage preparation mode" sections; restore the toolkit phases and gates through `harness decision present` and `publish-items`. Keep the harness tracker contract wording (gateway tools, not Azure calls). |
| Removed | `tracker-drafts.json`, `bundle.load_drafts`/`check_drafts`/`publish`/`_create_all`, `harness tracker publish`, `references/tracker-drafts.md`, `bundle.covers` and `tracker-published.json`. |
| Confirmation | `implementation-confirm` is the approval of one Story's Implementation Plan in breakdown (the toolkit's optional plan wait, made required). It requires the Story to exist in the tracker; on approval the hook pins the plan note, which satisfies `plan_approved`. No approval bundles several Stories. |
| Specs | `write-spec` owns technical specs (tech-spec, design doc, ADR, API contract) and drops its `implementation-plan` kind; it treats the approved plan as covering that kind and writes only missing kinds. `bmad-spec` leaves preparation. A spec that changes scope sends the work back to refinement. |
| Sessions | A work session tracks the entry item (Epic, Feature or Story); code baselines stay per work item. |
| Feature close | `finish-feature-development` gains a local mode: every child Story done, closing evidence recorded, one approval, Feature moved to done. |
| Idea route | Ends with a decision: continue into technical discovery, or stop with the brief or spec. |
| Refined Story | `harness begin` asks whether to run the BMad front half; changes to existing items go through `amend-workitems` or `enrich-work-item` before plan and Tasks. |
| Gates | Add `refinement-split` (required, no writes) for Gate 1. Reuse `publish-items` for Gate 2 and for each Story's Tasks. `implementation-confirm` wording drops "create work items" and names one Story's plan. |
| Local tracker | The toolkit's `local` destination is the harness local tracker, written through the gateway; readable drafts in `Tickets/Ready/` stay the review surface. |
| Docs | `six-stage-onboarding.md`, `workflow-storyboard.md`, `harness-stage-guide.md`, the harness skill, changelog. |
| Trial setup | Prepare hook trust and MCP tool approval for the isolated Codex home through a recorded, human-approved step. |

## Verification

- Unit tests: catalog stage and requirement wiring; `implementation-confirm` refuses a Story that is
  not in the tracker; the hook pins the plan note on approval; `publish-items` binds toolkit writes
  to the shown content; removed commands and files are gone; `write-spec` skips kinds the approved
  plan covers; `finish-feature-development` local mode refuses while a child Story is open.
- Retire or rewrite `tests/harness/test_bundle.py` and the bundle-order contract test.
- Live: rerun DAY-001 on a fresh fixture with hook trust and MCP approval prepared, through
  refinement, plan approval and `start-ticket`, with one code edit attempted before and after
  linking. Stop before implementation.

## Decisions (owner, 2026-10-15)

1. Stories and Tasks are approved separately, in the toolkit's order: one `publish-items` for the
   Stories, then, per Story, its plan and its Tasks.
2. No compatibility path: everything is still testing. `tracker-drafts.json` and
   `harness tracker publish` are removed outright.
3. One plan per User Story; no aggregate plan.
4. Enrichment follows the toolkit: formatted Stories, Features with formatted Stories, and Epics
   are only checked (`validate-artifact`); only what fails is enriched.
5. The `codex_workflows` step lists and templates are not restored: the harness skills already
   carry the Feature-stack sequences, and the toolkit owns work-item templates. What returns is the
   catalog wiring for `review-pr`, `resolve-ticket` and the Feature-stack skills.
6. Every created document or work item is shown for approval, then saved through the selected
   tracker. Work items are the source of truth; plans, specs and Tasks derive from them.
7. An already-refined Story: ask the user whether to run the BMad front half. If it changes anything,
   amend the work items first (`amend-workitems` for a tree, `enrich-work-item` for one Story), then
   the plan and Tasks, and approve them again.
8. Spec ownership: the toolkit's Implementation Plan is the Story's contract (every acceptance
   criterion mapped, Tasks derived from it). `write-spec` owns the technical specs with its critic
   review and drops its weaker `implementation-plan` kind. `bmad-spec` stays on the idea route.
9. A work session tracks whatever the user starts with: an Epic, a Feature or a Story.
10. A Feature closes without Git delivery through `finish-feature-development` in a local mode.
11. The idea route may stop at a product brief or spec; the user chooses whether to continue.
12. No aggregate confirmation: each Story's plan approval is its `implementation-confirm`, followed by
    its Task approval, as the toolkit's fan-out does it.

## Evidence

- Trial `20261015-day001-planning-gate-02` (parent report): hooks inactive until trusted, MCP tools
  blocked by Codex approval policy, the drafts-file deadlock, and BMad discovery and elicitation
  observed live.
- Source reads: agile-backlog-toolkit `/mnt/DATA/Projects/Personal/agile-backlog-toolkit` at
  `e7ae82c`; codex-workflows-plugin `/mnt/DATA/Projects/Personal/codex-workflows-plugin` at `75c22f0`.
