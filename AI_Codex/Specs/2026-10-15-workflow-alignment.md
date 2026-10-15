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

Companions: [backlog design detail](2026-10-15-backlog-workflow-in-six-stage-design.md) (today's
six-stage route, where trial 02 stalled, who approves what, and what the code-change gate reads).
Rendered diagrams: [this document](2026-10-15-workflow-alignment-diagrams/),
[the backlog design](2026-10-15-backlog-workflow-diagrams/).

## Principles

1. Each source's workflow runs as written: its phases, gates, read-backs, audits and critic reviews.
   The harness adds no parallel mechanics for what a source already owns.
2. Tracker first. Work items exist in the selected tracker, read back, before the Story plans are
   approved and before code changes.
3. Every tracker write goes through the harness gateway and its approval windows; every human
   decision goes through `harness decision present`.
4. What each stage needs and produces is declared in `config/prepared-workflows.json`. Nothing in the
   harness's own decisions depends on version control; Git-specific steps run only with Git delivery.

## The whole route

```mermaid
flowchart TD
    REQ[User request, idea, or work item] --> BEGIN["harness begin<br/>setup, work session, saved request"]
    BEGIN --> ROUTE{What did the user bring?}
    ROUTE -- "an idea to shape" --> IDEA["BMad product skills<br/>brainstorm, forge, research,<br/>brief, product spec"]
    IDEA --> DISC
    ROUTE -- "a request, draft, or work item" --> DISC

    subgraph BMAD["BMad: the approach"]
        DISC["Discovery<br/>bmad-build step 1: clarify and route"] --> PLAN["Planning<br/>bmad-build step 2: approach draft<br/>bmad-advanced-elicitation methods"]
        PLAN --> HARD["Hardening<br/>bmad-review at the chosen depth"]
    end

    subgraph ABT["agile-backlog-toolkit: the backlog"]
        HARD --> REF["Refinement<br/>check format, enrich what fails,<br/>decompose, size, create, read back, audit"]
        REF --> BRK["Breakdown per Story<br/>Implementation Plan, Tasks +<br/>Staging/Review/Breakdown, hours"]
        BRK --> VAL["validate-artifact on what was created"]
    end

    subgraph HAR["harness: the contract"]
        VAL --> PREP["Preparation<br/>bmad-spec companions, risk,<br/>verification, manifest"]
        PREP --> CONF{{"implementation-confirm<br/>approves the Story plans"}}
    end

    subgraph CW["codex-workflows: delivery"]
        CONF --> EXE["Execution per Story<br/>start-ticket, write-spec if needed,<br/>implement-story"]
        EXE --> VER["Verify<br/>review, review-pr, resolve-ticket"]
        VER --> FEAT["Feature close<br/>stack merge and finish (Git delivery),<br/>or finish locally"]
    end
```

## Front half: BMad

| Stage | BMad skill | Produces |
| --- | --- | --- |
| Discovery | `bmad-build` step 1 (rendered by `harness begin` into `_bmad/render/`) | Clarified request, route, initiative choice, code map |
| Planning | `bmad-build` step 2, `bmad-advanced-elicitation` | The approach draft and its memlog; depth and method choices |
| Hardening | `bmad-review` | Triaged findings; consequential choices settled |
| Idea route | `brainstorm-ideas`, `forge-idea`, `research-decision`, `product-brief`, `product-spec`, `plan-initiative` | A shaped idea before technical discovery |
| Any stage, as needed | `bmad-correct-course`, `bmad-project-context`, `bmad-deep-recon`, `bmad-qa-generate-e2e-tests` | Change of direction, instruction drift, reconnaissance, end-to-end tests |
| Preparation | `bmad-spec` | Spec and companions for each Story |

BMad's approach draft is the input to refinement. It is carried as a reviewed companion, not
approved as a plan: the execution contract is each Story's Implementation Plan.

## Middle: the backlog (agile-backlog-toolkit)

```mermaid
flowchart TD
    IN[Input from Hardening] --> FMT{"Already a formatted item?<br/>validate-artifact"}
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
    SZ -- no --> BRK["generate-breakdown-work-items per Story<br/>plan saved first, Tasks + Staging/Review/Breakdown,<br/>hours capped at capacity"]
    BRK --> G3{{"Approve Tasks<br/>(publish-items)"}}
    G3 --> C2["Create Tasks, read back,<br/>Breakdown Done + receipt"]
```

## Back half: delivery (codex-workflows)

```mermaid
flowchart TD
    CONF{{"implementation-confirm"}} --> NEXT[Next Story in order]
    NEXT --> ST["start-ticket<br/>link the work session, move to in progress<br/>(Git delivery: check out the key branch)"]
    ST --> SP{"Spec kinds still missing?<br/>spec_runtime plan"}
    SP -- yes --> WS["write-spec<br/>draft, Actor-Critic review (max 3),<br/>publish versioned artifact"]
    SP -- no --> IMP
    WS --> IMP["implement-story, per Task<br/>architect, failing test, implement,<br/>check, deslop, commit (Git delivery)"]
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
    FC -- no --> FIN["finish-feature-development<br/>(local: evidence and done)"]
```

## Sequences by starting point

Every sequence starts with `harness begin`, which checks setup, routes the work session and saves
the exact request. The four starting points differ in what refinement has to do.

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
        H->>B: product skills (brainstorm, forge, research, brief)
        B-->>U: shaped idea, product brief or spec
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
    K->>U: publish-items: create the Tasks
    K->>T: create Tasks, Breakdown Done
    H->>U: implementation-confirm (Story plans)
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
        K->>U: approve Tasks and hours
        K->>T: create Tasks, Breakdown Done
    end
    H->>U: implementation-confirm (all Story plans in scope)
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
        K->>U: approve Tasks and hours
        K->>T: create Tasks, Breakdown Done
    end
    H->>U: implementation-confirm (the Feature's Story plans)
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
        K->>U: approve Tasks and hours
        K->>T: create Tasks, Breakdown Done
    end
    H->>U: implementation-confirm (this Story's plan)
    H->>T: start-ticket: in progress, session linked
    Note over H,T: delivery for this Story
```

### Short path for a Story that is already refined

When the Story already has its Tasks in the tracker and an approved Implementation Plan, the
code-change requirements are met as soon as `start-ticket` links it. The `implement-approved-item`
route (setup → build → verify) then applies without repeating discovery and refinement. Whether
the full BMad front half should still run in that case is open question 1.

## Approvals per starting point

| Starting point | Split | Create items | Create Tasks | Story plans |
| --- | --- | --- | --- | --- |
| Idea or draft | Gate 1 per decomposed level | 1 `publish-items` per level | 1 `publish-items` | 1 `implementation-confirm` |
| Epic | Gate 1 per Feature | Features, then Stories | 1 `publish-items` across Stories | 1 `implementation-confirm` |
| Feature | Gate 1 when Stories are missing | Stories when missing | 1 `publish-items` across Stories | 1 `implementation-confirm` |
| User Story | split plan only when oversized | sub-stories only when split | 1 `publish-items` | 1 `implementation-confirm` |

Already formatted items are only validated; updates to existing items need their own approval.

## What changes in the harness

| Area | Change |
| --- | --- |
| Catalog | New `refinement` stage after `hardening` preparing the toolkit skills and tracker operations. `execution` prepares `start-ticket`, `write-spec`, `implement-story`; `verify` prepares the review stage, `review-pr` (Git delivery), `resolve-ticket`, and the Feature-close skills. Stack skills are prepared only with Git delivery. |
| Skills | Remove the three six-stage "draft mode" sections; restore the toolkit phases and gates through `harness decision present` and `publish-items`. |
| Removed | `tracker-drafts.json`, `bundle.load_drafts`/`check_drafts`/`publish`/`_create_all`, `harness tracker publish`, `references/tracker-drafts.md`, `bundle.covers` and `tracker-published.json`. |
| Confirmation | `implementation-confirm` binds the Story plans in scope, the manifest and companions; it requires each Story to exist with Tasks; on approval the hook pins the plan notes, which satisfies `plan_approved`. |
| Gates | Add `refinement-split` (required, no writes). Reuse `publish-items`. Reword `implementation-confirm`. |
| Local tracker | The toolkit's `local` destination is the harness local tracker, written through the gateway; readable drafts in `Tickets/Ready/` stay the review surface. |
| Docs | `six-stage-onboarding.md`, `workflow-storyboard.md`, `harness-stage-guide.md`, the harness skill, changelog. |
| Trial setup | Prepare hook trust and MCP tool approval for the isolated Codex home through a recorded, human-approved step. |

## Decisions (owner, 2026-10-15)

1. Stories and Tasks are approved separately, in the toolkit's order.
2. No compatibility path: everything is still testing. `tracker-drafts.json` and
   `harness tracker publish` are removed outright.
3. One plan per User Story; no aggregate plan.
4. Enrichment follows the toolkit: formatted Stories, Features with formatted Stories, and Epics
   are only checked (`validate-artifact`); only what fails is enriched.
5. The `codex_workflows` step lists and templates are not restored: the harness skills already
   carry the Feature-stack sequences, and the toolkit owns work-item templates. What returns is the
   catalog wiring for `review-pr`, `resolve-ticket` and the Feature-stack skills.

## Open questions

1. A Story that is already refined (Tasks and approved plan exist): run the BMad front half, or go
   straight to `implement-approved-item`?
2. Spec ownership: `write-spec` plans spec kinds per ticket (`spec_runtime`: for a feature,
   design-doc + tech-spec), while `bmad-spec` writes companions in preparation and the toolkit writes
   the Implementation Plan. Which one owns the technical spec, and should `write-spec` treat the
   approved plan and companions as already covering its kinds?
3. Work sessions for an Epic or a multi-Story Feature: one session that relinks Story by Story, or
   one session per Story?
4. Closing a Feature without Git delivery: `finish-feature-development` in a local mode (evidence
   and done), or leave the Feature open for a person?
5. The idea route: should it always continue into technical discovery, or may it stop at a product
   brief?
6. `implementation-confirm` across an Epic: one approval for every Story plan in the Epic, or one
   per Feature?

## Evidence

- Trial `20261015-day001-planning-gate-02` (parent report): hooks inactive until trusted, MCP tools
  blocked by Codex approval policy, the drafts-file deadlock, and BMad discovery and elicitation
  observed live.
- Source reads: agile-backlog-toolkit `/mnt/DATA/Projects/Personal/agile-backlog-toolkit` at
  `e7ae82c`; codex-workflows-plugin `/mnt/DATA/Projects/Personal/codex-workflows-plugin` at `75c22f0`.
