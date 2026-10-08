---
name: harness
description: Default entry point when the user asks to add, build, change, or fix a meaningful feature in a project, even if they do not mention the harness or provide a tracker item. Start with technical discovery for feature requests, then follow the product and delivery workflow as requested. Also use when the user asks to take an idea or work item through the whole process, asks what comes next in a harness run, or asks how the process works. Keep small mechanical edits on the direct path.
---

# Harness

Follow [the workflow storyboard](../../references/workflow-storyboard.md) for stage entry and exit,
review surfaces, and Back/Pause/Resume/Cancel/Complete behavior. This skill supplies the
stage-specific details. Each stage consumes the previous stage's output; none re-invents it. Hooks
enforce the rules that must never depend on the model remembering them.

```
 idea / work item
      │
 0 DISCOVER ──── bmad-build: read request → investigate (subagents) → plan + batched questions → Deepen → approve
      │           plan-initiative: ideate or shape a product idea when selected
      │
 1 BACKLOG ───── generate-work-item → enrich-work-item → decompose-backlog → generate-breakdown-work-items
      │           (top ancestor draft)  (team format)     (Epic→Features→Stories,  (Tasks + Staging/
      │                                                     points)                  Review/Breakdown)
      ├── G1  Feature Owner / PO reviews the complete batch before any tracker write
 2 TECH PLAN ─── start-ticket → write-spec (Actor-Critic)
      ├── G2  Tech Lead approves the spec
 3 BUILD ─────── implement-story: per Task architect → tdd → implement → check → deslop → commit;
      │           Story done: bmad-qa-generate-e2e-tests → prove-it-works
 4 VERIFY ────── review: review-story-preflight → thermos ∥ bmad-review (edge cases, claims, gaps) → triage → fixes → verdict → branch-and-pr (draft)
      ├── G3  Feature Owner validates in staging
      └── G4  a human publishes and approves the pull request
```

A change of direction at any stage (a new constraint, a failed assumption, a rescoped goal) goes
through `bmad-correct-course`: it assesses impact on the plan, spec, and work items, proposes the
changes, and routes back to the earliest stage whose approved output the change invalidates.

Stacked Feature work (several Stories under one Feature) runs stage 3–4 per Story inside
`feature-implementation`, then `merge-story-stack-into-feature` and `finish-feature-development`.

## Complete onboarding, then select a project work session

The plugin ships the `harness` command. Use `harness` from the shell path when available. If it is
not available, run the sibling `bin/harness` executable using the absolute plugin path derived from
this skill's own location; do not ask the user to find the path, change their shell path, or install
the plugin again. Report a missing command only if neither the shell command nor the bundled
executable exists.

Use the project path already supplied by the host or the user. Run
`harness bootstrap --inspect --repo <project>` to read shared project settings and tracker status.
Complete onboarding before routing, starting, or resuming a work session. Invoke the `bootstrap`
skill when setup is incomplete, this project's language is unconfirmed, or `bmad_runtime.ready`
is false. Language, settings,
local tracker preparation, runtime setup, trust, and required sign-in are onboarding actions;
none requires a work session or workflow. Preserve the original request while setup is pending.
Verify setup and language confirmation, then run
`harness work-session route --request "<exact user request>" --repo <project>` immediately before
starting product or engineering work. The route
command only reports candidates; it never starts or resumes a session. If it returns
`continue_active`, use that exact session. If it returns `start_new`, create a session with
`harness work-session start --request "<exact user request>" --repo <project>`. If it returns
`ask_user`, show all unfinished project sessions from `candidates`, their requests and statuses,
and **Start a new session** as clickable choices. This includes sessions for a different ticket:
the human chooses whether to switch or keep the current work. A paused or stopped session requires
the human to choose it before running
`harness work-session resume <id> --repo <project>`. Never silently resume paused or stopped work.

Keep the selected work-session ID as required context after onboarding. Every workflow command
must include `--session-id <id>`, including `start`, `checkpoint`, `status`, `list`, `pause`,
`resume`, `back`, `cancel`, `complete`, and discovery `render`. Session checkpoints are stored with that session.
Project settings such as tracker and planning folder remain shared. Onboarding establishes the
tracker and runtime before session creation. A project work session does not require Git, a project
contract, or starting the checkout-bound implementation session.

Use the selected session's exact saved request as the run context. Pass the project root, session
ID, bundled command, isolated preferences environment, checkpoint, and next action to any delegated
agent; do not make it rediscover the project or reset confirmed setup. Inspect is read-only. Pending
questions and a suspended harness remain explicit; do not resume a stopped run or replace invalid
saved progress automatically. Use the host adapter described in
[human-decisions.md](../../references/human-decisions.md) for human decisions.
Start the workflow with the selected session's exact original request:
`harness workflow start --session-id <id> --request "<original request>" --repo <project>`. If that
session already has a workflow, show its saved checkpoints and let the user resume or cancel it
before starting another. Do not start a session or workflow to complete onboarding.
Host trust and sign-in remain human actions where required. The selected tracker and its manifest
provide the work-item capabilities for planning; do not start a second tracker or review-source
setup during discovery, ideation, or backlog drafting. Mark the workflow complete when its
requested outcome is finished.

Use the inspection's current `repository.has_committed_head`, `tracker_storage`, and `workflow`
fields when resuming. A saved note about a missing commit describes the past. Recheck current
state and continue the pending product or engineering step. If the bundled local tracker has missing
folders, bootstrap prepares them without a user question.

`back`, `pause`, `resume`, and `cancel` are workflow actions. Use native controls; never ask the user
to type these actions. Include Back on a review screen when an earlier decision can be revised.
Accept Pause at any point without asking a second question. Checkpoints never grant
permission for an external write. Resume rechecks files, tracker, and approvals before work.

### Suspend harness checks on the human's request

Only the human can suspend the harness: the hook records it when they send `harness suspend` as its
own message, and no command lets an agent do it. When they want to continue ordinary work outside
the harness, use `suspend-harness` to ask them to send it. It works before setup and with invalid
settings or an unavailable tracker. Verify with `harness suspension status --repo <project>`; until
it reports `"mode": "suspended"`, the checks still apply.

While suspended, continue the human's ordinary work without harness workflow, tracker, branch,
commit, review, decision-wait, or question-wording checks. Approval and decision clicks are still
recorded, a pending decision is kept rather than answered, and direct edits to human-owned
control/evidence records remain protected; host permissions and other plugins are independent.
Preserve the existing workflow, settings, tracker, and evidence. Workflow/session pause and
`skip-tracker` are different operations and do not suspend all checks.

To restore enforcement, use `resume-harness` (`harness suspension resume --repo <project>`, or the
human sends `harness resume`). Resume restores checks without opening an approval window or
accepting old readiness evidence. Never ask the human to suspend the harness to get past a refusal.

Once onboarding is complete and a work session has been selected, save its initial checkpoint
with setup already verified and the original request as the next action. Save another checkpoint
at each material review point. Before a review question, record
the artifact path, pending decision, and next action; include `--artifact <path>` so the saved point
captures its content digest. When the user says Pause, save any new progress first, then run
`harness workflow pause`. On Resume, show `harness workflow list` and offer the current point and
earlier review points in one choice. After revising an earlier point, rebuild only affected drafts
and save a new checkpoint before asking for another decision.

## Prepare each stage

At the start of each stage, run
`harness workflow prepare --route <route> --prepared-stage <stage> --request "<exact request>" --repo <project>`,
adding `--available <tool>` for each tracker or SCM tool your host offers. Use what it returns: the
project and harness references, recommended skills, operations, expected outputs, checks, and
recovery. `harness workflow routes` lists the routes: `investigate-request` for a named request,
`explore-idea` for ideation, `prepare-artifacts` for backlog and specification work,
`implement-approved-item` for build and verify, `resume-work` to continue saved work, and
`suspend-checks` when the user asks to work outside the harness. The step is `ready` only when its
inputs are present and you confirmed every tool it needs; report anything missing instead of
improvising around it. The stage sections below add what the prepared step does not cover.

## Stage 0: Technical discovery

For an assigned ticket or request to change an existing product, invoke `bmad-build`. It renders
the bundled clarify-and-route and plan templates with this project's verified context and selected
work-session ID. Follow only the returned absolute entry; the snapshot is pinned to the session
and verified on resume. Onboarding prepares the BMad runtime (`_bmad/`). Do not install or fetch
workflow infrastructure during discovery. For broad or risky
work, BMad's `bmad-spec` (a capability contract) and `bmad-architecture` (decisions that keep
separately built parts consistent) are available; `bmad-build` uses `bmad-prd` when the requested
behavior is too unclear to investigate. `bmad-build` investigates with subagents, uses `bmad-deep-recon` for
unfamiliar code or domains, flags drift between the code and the project's agent instructions (fixed
with `bmad-project-context`), keeps a decision memlog beside the plan, and offers **Deepen**
(adversarial and edge-case review, elicitation, party mode) at its approval checkpoint. Do not start implementation from this step. On approval, save the plan as a harness workflow
checkpoint and pass it to Stage 1 as the source for work-item drafting. The Stage 0 approval does
not publish tracker items; the normal backlog review and write gates still apply.

For a ticket in an external or local harness tracker, check `workflow_tracking_status`, use
`tracker_get_work_item` for the named item and `tracker_list_children` for relevant parent context.
Use `tracker_search_work_items` only when a named item cannot be retrieved directly. For an explicit
file or path such as `backlog/DAY-001-task-counts.md`, read that file directly. This lookup must not
move the ticket, create a branch, start a session, or publish an artifact. Use BMad's file-based
ticket tree only when the user explicitly chose that store.

An existing project file does not need a tracker-issued key for discovery. The local tracker creates
its own keys when backlog items are published later. Do not run `harness tracker stage` for the
bundled local tracker or ask the user to initialize it during planning.

Git is optional. Discovery, planning, local work-item drafts, and workflow checkpoints must continue
when the folder has no Git metadata or has no commit yet. Do not request an initial commit, branch,
or checkout-bound implementation session to read or save a plan. The selected project work
session still owns those plans and checkpoints. Checkout-bound session and commit rules apply
when the repository has a committed Git baseline and the workflow reaches governed code changes.

Use `plan-initiative` when the user explicitly wants to explore what problem or product to pursue,
or when the intended outcome is not yet identifiable. Its optional brainstorming, idea-forging,
research, brief, requirements, experience, and architecture routes remain available. A clear request
that only needs a product contract can still go directly to `product-spec`. Do not make ideation a
prerequisite for an assigned change.

The BMad plan is the feature-level strategy. Later `write-spec` work must use it as an input and
cover only story-level details needed for implementation. Do not repeat Stage 0 investigation or
silently change its accepted decisions. Finishing Stage 0 never implies permission to create or
publish tracker items.

### Offer the starting point

When the request names an existing task or ticket, follow the storyboard directly; do not ask whether
to investigate or draft new work items. When the request is a feature idea with no clear starting
point, ask this one structured question:

- Header: `Starting point`
- Question: `What would you like to do with this idea?`
- Option `Investigate first`: `Review the repository and prepare a technical implementation plan.`
- Option `Draft work items`: `Use the request as provided and prepare work items now.`
- Option `Explore the idea`: `Shape or challenge the idea before planning the technical work.`

Use the host adapter's supported blocking presentation or chat-and-wait fallback. Do not add an `Other` option; the Codex question UI supplies its default free-text field.
Prepare this routing decision with `harness decision present --allow-free-text`; for a direct Codex
control use id `starting_point`. The existing `plain-questions` hook validates the question before
display. Use the available native control. If delivery fails, quietly run `harness decision fallback`
and re-ask the same question by the next method, including ordinary chat when needed. Preserve
the choices and progress and continue this same run after the reply; do not abandon it or expose
internal question-tool errors. The shared human-decisions contract applies to every later question too.

The choice is routing, not approval: it never opens an approval window. `Investigate first` invokes
`bmad-build`; `Draft work items` enters Stage 1; `Explore the idea` invokes `plan-initiative`.
Continue directly when the user already chose a starting point, named an existing task, directly
invoked a planning skill, or explicitly asked to create or modify a work item.

## Stage 1: Backlog

1. **Top ancestor.** `generate-work-item` drafts the highest item in the tree (usually an Epic) from
   the product spec, user's idea, or an existing item. When a product spec exists, preserve its
   `CAP-N` identifiers and companions rather than re-inventing the intent. The **Descrição Original** section keeps the source text
   verbatim. The top ancestor can be a Feature or a User Story: neither needs a parent, so do not
   ask for or invent one. When the source is an item that must stay intact (for example, the
   original of a copied item), create a new item and name the original in plain text (id and
   title, for example `Idea 4007`). Never link to it, and never write `#4007` or its URL in a
   description or comment: Azure DevOps turns a mention into a link, and links are two-way. Rule
   `protected-items` blocks protected ids in id fields and in text.
2. **Enrich** it (`enrich-work-item`) into the team format.
3. **Decompose** (`decompose-backlog`, tree mode for an Epic): Features, then Stories with points,
   one outline at GATE 1 and one body batch at GATE 2. Points go into the Azure points field.
4. **Break down** each Story that will be built next (`generate-breakdown-work-items`): atomic Tasks
   aligned to the acceptance criteria, plus Staging, Review, and a done Breakdown Task.
5. `validate-artifact` on anything the user edited by hand. Check the selected tracker's hierarchy,
   labels, and required values before publishing the batch. In Linear, confirm Story and Task
   labels exist before the first item is created. Explain where every Task will be visible.

## Stage 2: Technical plan

`start-ticket` on the Story (moves it to in progress), then `write-spec`. The spec takes the
Story, its acceptance criteria, its covered `CAP-N` values, its Tasks, and any adopted UX and
architecture companions as input. It decides the Story-local *how*: affected modules, contracts,
test strategy, and implementation details. It cannot override an upstream `AD-N` or product
constraint silently. Present its exact revision through the best available review surface for
**G2** and stop until the user approves. A path or short summary alone is insufficient.

## Stage 3: Build

`implement-story`. One Task, one verified commit, in breakdown order. When the Story is done, it
generates API and end-to-end tests for the delivered behavior with `bmad-qa-generate-e2e-tests`
before `prove-it-works`.

## Stage 4: Verify

`review`. The requirements check first, then thermos alongside `bmad-review`'s edge-case and
verification-gap lenses (the edge-case lens also falsifies the plan's claims and checks deletions),
one triage of all findings, fixes, a verdict for HEAD, and the draft PR.

## Talking to the user

The person driving the harness knows the goal, not the harness. Every message and question is for
them:

- Only raise what blocks the thing they are doing right now. Everything else (leftover files, old
  tools, follow-ups) waits for one short list at the end of the stage.
- Plain words. No file names, code, rule names, tool names, or batch ids unless they ask. Describe
  what a thing does instead ("the setting that hides local files from git").
- Ask in one of two shapes only ([human-decisions.md](../../references/human-decisions.md)): a
  **menu** through `harness decision present` (one choice, up to three options, each with
  `--detail` saying what happens for them and the `--recommended` one marked), or a **question
  batch** (every open question in one chat message, each with options and a recommendation).
  Never ask batch questions one at a time.
- Every turn ends with a menu, a question batch, or a `Next:` line followed by continued work.
- Apply `generate-plain-language-documentation` writing rules to labels, questions, updates, and
  artifact summaries as an inline prose pass; do not run its standalone intake for every message.
- Continue through reversible local drafting and checks within a stage. Stop only for missing
  information, a material decision, an actual protected write, or a complete artifact review.

Hook `plain-questions` checks every question before it is shown and sends back one that is too long,
asks several things, or needs the harness's vocabulary to understand.

## The approval protocol (every tracker or SCM write)

Hook `approval-required` blocks every write to a tracker or SCM (work items, links, comments, pull
requests, threads, branches, `git push`) unless the user has opened an approval window. To open one:

1. Say in plain words what will be written: which items, with their titles, and what changes.
2. Present the complete relevant artifact or batch through the best available host surface. Ask one
   `--approval` menu with two options, labelled exactly `Approve` and `Not now`, passing the batch
   with `--artifact`. The human's click or typed `Approve` opens the window for
   `approvals.window_minutes` (default 20). The window covers only the work session it was opened
   in; another session needs its own approval. Asking again for the same unchanged batch while the
   window is open returns the earlier approval instead of a new question.
3. Make only the writes you described. Anything new needs a new question.

If a native control is unavailable, the menu falls back to chat: show the review and the returned
`menu`, end the turn, and wait for the real human reply; do not write while approval is pending.
`harness revoke` closes a window early.

You cannot open the window yourself: approvals are recorded only from the user's own prompt or
click, a question that arrives with answers already filled in is refused, and hook `human-owned`
blocks any agent write to the records. Gates G1, G2, and G4 map to these approvals.

## Enforced rules (hooks)

| Rule | What it blocks |
| --- | --- |
| `human-owned` | agent writes to `.harness/settings.json`, and to approval, manual-check, question, session, tracker-trust, tracking-mode, or suspension records |
| `tracker-invalid` | tracker and SCM writes while the selected tracker is missing, untrusted, or lacks its values |
| `plain-questions` | questions to the user that are long, ask several things, contain file names, code, or internal names, or come with answers filled in |
| `approval-required` | tracker/SCM writes and `git push` without an open approval window |
| `protected-items` | any write, link, or child on a protected work item, even with approval |
| `tests-with-code` | commits that change source files with no test change in the commit or on the branch |
| `generated-files` | hand edits to generated files |
| `guarded-paths` | commits to guarded paths without check or manual evidence for the staged tree |
| `draft-reviewed-prs` | non-draft pull requests; pull requests without a `ready` verdict and passing checks for HEAD; publishing drafts or voting |
| `history-preserved` | rewriting branch history: rebase, squash merges, force-push, `filter-branch`, completing a pull request by squash or rebase |
| workflow | code changes without an active session for this checkout (`harness session start`), new branches off the convention, the session's work item not in progress, code before an accepted spec, completion without evidence, protected branches |

When a hook blocks you, read its reason and fix the cause. Never retry through another tool or
route around it.

When the user asks to work outside the harness, use `suspend-harness`: the user sends
`harness suspend` as its own message, and the hook turns off every rule above except `human-owned`
while keeping the settings, tracker, and evidence. Only the user's own message can suspend the
harness. `resume-harness` turns the checks back on.

## Models per stage

| Stage | Where it runs | Model |
| --- | --- | --- |
| Backlog, spec, review synthesis | main session | the strongest model available (Opus-class), high effort |
| Architect candidates | design subagents | same as the main session |
| Implementation | main session | Opus-class at medium effort, or Sonnet-class; measure both on real Stories |
| Thermos reviewers | `agents/thermo-*` | pinned `model: opus` |

## Evidence of the run

Keep a short running record in the session: each gate's approval id, each created work item id,
each commit per Task, check evidence paths, and the verdict, so anyone can audit the run later.
