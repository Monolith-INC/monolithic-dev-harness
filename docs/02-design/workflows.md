---
title: Runtime Workflows
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
---

# Runtime Workflows

## End-to-end flow

```text
idea / work item
  -> 0 DEFINE    plan-initiative: use only the needed discovery / requirements / UX /
                 architecture skills -> product-spec with stable CAP-N ids and companions
                 stop and ask before starting tracker-backed work
  -> 1 BACKLOG   generate-work-item -> enrich-work-item -> decompose-backlog
                 -> generate-breakdown-work-items
                 G1: Feature Owner / PO approve the outline, then the bodies (one batch each)
  -> 2 TECH PLAN start-ticket -> write-spec (Actor-Critic)
                 G2: Tech Lead approves the spec
  -> 3 BUILD     implement-story: one verified commit per Task
  -> 4 VERIFY    review -> branch-and-pr (draft)
                 G3: staging validation
                 G4: a person publishes and approves the pull request
```

The `harness` skill conducts this flow. Stage 0 is optional when the input is already a defined
intent or an existing work item. Stacked Features run stages 2–4 once per Story inside
`feature-implementation`, on Story branches based on the Feature branch.

## Definition stage

```text
unclear idea
  |
  +--> brainstorm-ideas       missing options
  +--> forge-idea             untested central claim
  +--> research-decision      missing current evidence
  +--> product-brief          concise product narrative needed
  +--> product-requirements   multi-person or multi-epic agreement needed
  +--> experience-design      shared UX decisions can diverge
  +--> architecture-spine     cross-unit technical choices can diverge
  |
  `--> product-spec           canonical Why / CAP-N / constraints / non-goals / success signal
           |
           `--> ask whether to begin backlog drafting
```

These are independent tools, not a fixed waterfall. The product spec adopts load-bearing UX and
architecture artifacts as companions. Planning creates no tracker item, branch, commit, or pull
request. The existing approval protocol begins when the user chooses to enter the backlog stage.

When a whole-harness request starts from an idea and the user has not selected a starting point,
the agent asks one structured question: **Plan the idea** or **Draft work items**. The first enters
Stage 0; the second enters Stage 1. The existing question hook validates that prompt before it is
shown. This routing choice is not an approval and opens no write window.

## Backlog stage

```text
source text (product spec, idea, or existing item)
  |
  v
generate-work-item    top ancestor draft (usually an Epic); Descrição Original kept verbatim
  |
  v
enrich-work-item      team format: O quê, Por quê, Comportamento, Critérios, Notas, Complexidade
  |
  v
decompose-backlog     tree mode for an Epic:
  |                     DECOMPOSE  Features (existing reused), Stories under each;
  |                                preserve CAP-N coverage when a product spec exists
  |                     GATE 1     one outline for the whole tree
  |                     DRAFT      Feature + Story drafts; Stories under new Features use
  |                                parent_id "pending:<feature draft>"
  |                     ENRICH     team format, Story Points per the 6-driver MAX
  |                     GATE 2     one batch: every body with points
  |                     CREATE     top-down: Features, then Stories under the real Feature ids
  |                     VERIFY     read back: parent chain, points field set
  |                     AUDIT      Epic slice -> Feature -> Story coverage; orphans, scope creep
  v
generate-breakdown-work-items   per Story: atomic Tasks + Staging + Review + Breakdown (done)
```

## Build stage (per Story)

```text
start-ticket (Story -> in progress) --> branch-and-pr: branch {category}/{key}-{slug}
  |
  v
for each Task, in breakdown order:
  architect         only when the Task adds or reshapes an interface
  tdd               failing test for the Task's acceptance criterion
  implement         smallest change that passes it
  check             configured checks; --staged before committing a guarded path
  deslop            remove AI slop from the Task's diff
  commit            one Task, one commit      <- tests-with-code, generated-files, guarded-paths
  transition Task   approval batch            <- approval-required
  |
  v
check on HEAD (clean tree) -> prove-it-works -> review
```

## Verify stage

```text
review-story-preflight   Story branch vs description, acceptance criteria, DoD -> ready | blocked
  |
thermos                  two parallel reviewers: correctness/security, maintainability
  |
fix VERIFIED findings    new commits; re-run checks and the pass that found them
  |
review_verdict.py        ready for HEAD (clean tree required)
  |
branch-and-pr            push + draft PR linked to the Story   <- approval-required,
                                                                   draft-reviewed-prs
```

## Orchestrated skill call

```text
agent --tools/call(skill, args)--> orchestrator
                                     | validate args against manifest.json   (reject: error)
                                     v
                                   task spawned (event-sourced queue)
                                     |
                         +---------> run skill handler
                         |           |
                         |    critiques or transient failure?
                         |      yes, retries left, output changed --+
                         +------------------------------------------+
                                     |
                         no critiques          same output + same critiques twice,
                                     |          deterministic/fatal failure, or
                                     v          retries exhausted
                                 completed  ---------------> stopped (state reported)
```

The orchestrator returns instructions and verdicts. The agent performs any provider call itself,
through the gateway or a tracker's own server, where the hook runtime sees it.

## Hook evaluation

```text
tool call
  -> repository has .harness/settings.json?        no  -> allow
  -> settings readable?                         no  -> deny writes, allow reads
  -> human-owned        writes settings or records?     -> deny
  -> tracker-invalid    tracker write while the selected
                        tracker is unusable?             -> deny
  -> protected-items    names or links a protected id?   -> deny
  -> draft-reviewed-prs PR not draft / not reviewed /
                        checks missing / publish / vote?  -> deny
  -> approval-required  tracker/SCM write or git push
                        without an open window?          -> deny
  -> generated-files    hand edit of a generated file?   -> deny
  -> git commit?        tests-with-code, guarded-paths   -> deny
  -> workflow policy    active session, branch convention,
                        state, spec, evidence, protected
                        branches, stack order            -> deny
  -> allow (and log the write to the open approval window)
```

## Sessions

```text
start-ticket
  -> work item's branch checked out (branch_template + the tracker's ids.branch_key)
  -> tracker_transition_work_item in_progress        (approval)
  -> harness session start <work item>               binds the item to this checkout
implement-story / review
  -> code changes allowed while the session is active, the item is in progress, and a spec is
     accepted (the workflow policy reads the session's item, not the branch name)
  -> harness session pause / resume                  when work stops and starts again
resolve-ticket
  -> tracker_transition_work_item done               checked against the session's item
  -> harness session close                           frees the checkout
```

A detached HEAD, another branch in the same checkout, or an unreadable session record means no
active session, so governed code changes are refused until one is started.

## Approval protocol

```text
agent                          you                      prompt hook          pre-tool hook
  | batch HB-7Q2K:              |                            |                     |
  |  1 Feature, 3 Stories,      |                            |                     |
  |  3 parent links             |                            |                     |
  |---------------------------->|                            |                     |
  |                             | "approve HB-7Q2K"          |                     |
  |                             |--------------------------->| window open 20 min  |
  | wit_work_item_write[create] |                            |                     |
  |---------------------------------------------------------------------------->  | allow, log write
  |                                                                                 |
  | (no window, or window expired)                                                  |
  |---------------------------------------------------------------------------->  | deny: approval-required
```

The agent cannot open a window: approval records are human-owned. `harness revoke` closes windows.

## Examples

### Idea to backlog tree

```text
You:    Take "students can add a profile photo" through the backlog stage. pt-BR.
Agent:  drafts the Epic, enriches it, proposes:
          Feature 1  Photo upload and cropping   Stories: 5, 3, 3 pts
          Feature 2  Avatar across the app       Stories: 3, 2 pts
        GATE 1: approve the outline?
You:    merge the two avatar Stories
Agent:  shows every body with points
        GATE 2: batch HB-4F9A (1 Epic, 2 Features, 4 Stories, 7 parent links)
You:    approve HB-4F9A
Agent:  creates top-down, reads back parents and points, reports coverage
```

```text
Epic: Profile photo
|-- Feature 1: upload and cropping
|   |-- Story (5 pts)  pick and crop an image
|   |-- Story (3 pts)  store and serve resized images
|   `-- Story (3 pts)  replace and remove the photo
`-- Feature 2: avatar across the app
    `-- Story (5 pts)  avatar in lists and headers
        |-- Task  avatar widget with initials fallback
        |-- Task  use it in list tiles
        |-- Staging
        |-- Review
        `-- Breakdown (done)
```

### A rule stopping a commit

```text
Agent:  git commit -m "feat: avatar widget"
Hook:   [harness tests-with-code] this commit changes 2 source file(s) (e.g. src/profile/avatar.ts)
        and neither the commit nor the branch changes a test matching ['src/**/*.test.ts'].
        New code ships with tests.
Agent:  adds src/profile/avatar.test.ts, runs the check, commits again -> allowed
```

### A guarded path with no automated suite

```text
Agent:  stages infra/main.tf, asks you to validate the change by hand
You:    validated in the sandbox — harness manual-check infra ok
Hook:   [harness] manual check infra recorded for staged tree 3f2a91c0d4e1
Agent:  git commit -> allowed (the evidence matches the staged tree exactly)
```
