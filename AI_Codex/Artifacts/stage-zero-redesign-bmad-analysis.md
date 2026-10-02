# Stage 0 redesign: BMad workflow analysis

Date: 2026-10-02
Status: evidence-based proposal for review; no workflow implementation changes made

## Goal

Redesign the harness's first planning step around the work developers usually receive: an assigned ticket or a product-owner request that names a desired change but may omit behavior, feasibility, technical fit, or implementation detail.

The starting ticket is evidence of requested work, not proof that the request is complete or technically sound. Stage 0 should help a developer understand the request, investigate the real repository, and prepare a reviewable implementation strategy and the supporting documents before backlog drafting or code changes.

Product ideation remains available as an optional route when someone explicitly wants to discover or expand product directions. It is not the default route for assigned work.

## What the BMad flows say

BMad does not impose one mandatory chain of product-discovery skills before every change. Its planning guide chooses a path by the state and size of the incoming intent.

### Assigned ticket or one coherent change: `bmad-build`

1. **Clarify and route (`step-01-clarify-and-route.md`).** Start with the request or named ticket. Resolve existing plan/workflow state; read the ticket and its parent context when applicable; load relevant product, design, and architecture documents; inspect repository and version-control state; check whether the request contains multiple independently shippable goals. The ticket is treated as starting intent, not permission to skip investigation or planning.
2. **Investigate and plan (`step-02-plan.md`).** Inspect the affected code and project records before asking the user. Record a code map with paths, symbols, what to reuse, and what not to change. Draft the implementation plan with ordered tasks, acceptance checks, design notes, verification, and open questions. Search for answers in the repository first; ask about remaining decisions that only a person can settle.
3. **Review the plan.** Self-check that each task is actionable, ordered, testable, complete, and coherent. Resolve blocking questions, then present the plan for a human decision. Approval makes the plan ready for development.
4. **Build, review, and present.** The later steps implement against the approved plan, run checks, review the result, and present delivery evidence.

This is the closest match for a developer handed an underdeveloped ticket. The strongest fit is the separation between request intake and repository investigation: do not interrogate the user about facts the code or project documents can establish.

### Intent is too thin or requires wider alignment

BMad's planning router uses additional skills only when the gap calls for them:

- `bmad-spec` records the agreed product contract: why, capabilities, constraints, non-goals, and success. It distills intent; it does not discover product strategy or produce the implementation plan.
- `bmad-architecture` records only non-obvious decisions that separately built pieces must share. It is a short consistency contract, not a detailed design for one ticket.
- `bmad-ticket` learns the codebase and team, then plans an epic's work in build order with coverage, dependencies, uncertainty, and verification. It is for work that needs several implementation sessions or coordinated stories.
- Product discovery skills such as brainstorming, idea-forging, briefs, and PRDs answer different questions. They are optional when the incoming work needs those answers; they are not prerequisites to building a normal assigned ticket.

BMad's size guidance is consequential: a clear local change may go directly to Build; one-session work gets one Build plan; multi-session coherent work is divided into stories; broad, high-risk, cross-system work gets shared product or architecture artifacts as needed.

## What the current harness does

The current `harness` entry point labels Stage 0 “Define the intent.” It routes an early idea through `plan-initiative`, whose primary output is a product spec. It allows a supplied work item that already has a complete product contract to skip Stage 0. It does not define a default path that takes an ordinary underdeveloped assigned ticket through codebase investigation and a full feature implementation strategy before backlog drafting.

The harness's later `write-spec` runs after backlog decomposition and produces Story-local technical detail. That is useful for implementation, but it is too late to discover that the proposed feature is infeasible, changes architectural boundaries, needs a migration, or should be divided differently before the backlog is created.

## Assimilation approach: follow Thermos

The current harness inventory is a map of reusable pieces, not a limit on what can be included. Use the same approach as the Thermos assimilation: bring the relevant open-source source package into the harness, preserve its source structure and license/attribution, then adapt the host integration and runtime connections needed for the harness. Do not author a parallel planning method from scratch.

For this redesign, `bmad-build` is the primary source package to assess and assimilate because it contains the ticket intake, repository investigation, planning, review, and handoff sequence closest to the intended default flow. Bring the supporting files and assets that its own workflow requires, not just its `SKILL.md`. Assess `bmad-ticket`, `bmad-spec`, and `bmad-architecture` as source components for the larger-work and artifact routes described by BMad; reuse or import them where the workflow calls for them. Keep BMad's optional product discovery paths available for requests that need them.

Before implementation, inventory the selected source package and its dependencies: skills, templates, references, prompts, configuration, runtime or renderer, method assets, and tracker assumptions. Import the needed source components with their attribution, then map host-specific invocation, tracker storage, approval checkpoints, and durable state to harness adapters. Any changes to imported workflow content should remain traceable to its BMad source. The harness may change when these pieces run to make technical investigation the first step for an assigned ticket, while preserving the source method rather than inventing a new one.

## Existing harness pieces and source components to assimilate

Use the table to identify harness capabilities that can be reused and BMad source components that may need to be brought in. It does not require the current harness to already contain every capability. The imported BMad workflow supplies the source method; harness components can provide integration where they already fit.

| BMad need | Reusable harness capability or source package | Gap or boundary to preserve |
| --- | --- | --- |
| Enter from an assigned ticket and load its context | `harness` workflow state; `start-ticket` and tracker read skills; `validate-artifact` | `start-ticket` changes tracker state and starts implementation work, so it is too late and too consequential to use as read-only Stage 0 intake. Stage 0 needs a safe read/resolve route. |
| Route based on what is known or missing | `plan-initiative` and `planning-artifacts.md` | The router currently centers raw product intent and a product spec; reshape its route for an assigned, incomplete ticket. |
| Research unknown domain or technical facts | `research-decision`; repository inspection instructions in `architect`, `write-spec`, and `generate-breakdown-work-items` | Reuse these research behaviors and source rules. Avoid duplicating them in a new generic research system. |
| Set product behavior and capability boundaries | `product-spec`; `experience-design` | Invoke only when behavior or interaction decisions are actually unresolved. `product-spec` owns the WHAT, not the technical HOW. |
| Set cross-unit technical invariants | `architecture-spine` | Use only when separate stories or components could diverge; it is not a per-ticket design document. |
| Produce an implementation plan and atomic tasks | `generate-breakdown-work-items` and its implementation-plan generation | It currently runs after a Story and acceptance criteria exist. Reuse its planning rules and output where appropriate, but move the feature-level investigation earlier only if its inputs and ownership can be cleanly adapted. |
| Produce the detailed technical specification | `write-spec` | It currently expects a decomposed Story and Tasks. Keep it for Story-level detail unless the redesign can reuse it without duplicating Stage 0's feature strategy. |
| Compare code structures before implementation | `architect` | It compares code sketches for an approved Task/Story. It may be invoked for a genuinely load-bearing design question, not as mandatory ceremony for every feature. |
| Preserve reviews, approvals, pause and resume | `workflow-storyboard.md`, `harness` and its hooks | Reuse existing checkpoints, review surfaces, protected-write approvals, and pause/resume state; don't invent a second gate system. |

## Proposed Stage 0 composition

Assimilate BMad's ticket-to-build source workflow and supporting files, then connect it to harness entry points and state. Existing harness skills may be reused where they match the source workflow; import missing source capabilities instead of recreating them. Any adaptation should be limited to integration and the agreed Stage 0 sequencing. Do not create a parallel specification format or duplicate capabilities. Not every ticket needs every skill or artifact.

1. **Resume or start.** Check for an active workflow and the ticket's latest known state. Resume existing analysis when possible. Keep the source ticket intact and record which revision is being assessed.
2. **Read the request in context.** Read the ticket, parent/related items, repository guidance, product and design documents, architecture decisions, recent relevant changes, and existing tests. Summarize the requested outcome, known constraints, and missing information without rewriting the request as fact.
3. **Check scope and route.** Decide whether this is one coherent change, several independent outcomes, or a larger coordinated feature. Use the shortest safe path. Route optional product discovery only when the user asks to explore what to build or the requested outcome itself cannot be identified.
4. **Investigate the actual system.** Trace relevant data, interfaces, modules, dependencies, persistence, user flows, error handling, and tests. Record the code map and existing patterns. Look up current official documentation when a library or platform detail affects feasibility. Use a small prototype or bounded experiment only when research cannot resolve a material technical uncertainty.
5. **Separate facts from decisions.** Resolve repository-answerable questions first. Distinguish product behavior the owner must decide from engineering choices the developer can recommend. Keep assumptions, risks, and unresolved questions visible; do not invent requirements to fill gaps.
6. **Compare feasible approaches.** For each serious option, state what changes, what can be reused, required tools or dependencies, data/API or migration impact, benefits, costs, failure modes, and evidence. Recommend an option with reasons. Do not add a library unless it solves a demonstrated need.
7. **Prepare the feature implementation strategy.** Create the smallest sufficient review package, normally containing:
   - confirmed request, user-visible outcome, boundaries, and success checks;
   - repository code map and conventions to reuse;
   - recommended design, affected components, data and interface changes;
   - alternatives and trade-offs, including whether dependencies or infrastructure changes are needed;
   - risks, edge cases, migration/compatibility needs, and unresolved owner decisions;
   - ordered implementation slices, dependencies, and verification plan;
   - supporting product, experience, or architecture documents only when their subject requires them.
8. **Challenge and review.** Check the proposal against failure scenarios, repository constraints, and a simpler alternative. Present the complete package—not only a path or summary—for a decision before creating backlog items or editing code.
9. **Hand off.** After approval, draft backlog work from the accepted strategy. Keep the later Story-level technical spec for details that genuinely depend on the final tasks. Do not repeat Stage 0 investigation or silently change the approved intent.

## Decisions that remain open

These are design questions for the workflow redesign, not answers to assume now:

- What signals distinguish an underdeveloped ticket that needs Stage 0 from a ready ticket that can start implementation planning directly?
- Should Stage 0's accepted strategy live as a feature-level artifact in the project docs, the AI continuity ledger, or both, and how should ticket references point to it?
- Which existing approval gates should protect the strategy review, backlog write, and later Story-level specification? The strategy review must happen before tracker publication if it can change scope or feasibility.
- How should a one-session ticket avoid duplicate planning between Stage 0 and the current technical-plan stage, while multi-story features preserve both feature-level decisions and Story-level detail?
- Which technical research or test actions can run automatically, and which require a bounded prototype or explicit user decision?

## Evidence consulted

BMad source material:

- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/docs/plan/choose-a-planning-path.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/docs/plan/define-requirements-and-a-specification.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/docs/plan/design-ux-and-architecture.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/docs/plan/break-work-into-stories-and-track-it.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-build/step-01-clarify-and-route.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-build/step-02-plan.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-build/plan-template.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-ticket/references/slice.md`

Current harness entry points:

- `plugins/monolithic-dev-harness/skills/harness/SKILL.md`
- `plugins/monolithic-dev-harness/skills/plan-initiative/SKILL.md`
- `plugins/monolithic-dev-harness/skills/write-spec/SKILL.md`
- `plugins/monolithic-dev-harness/references/workflow-storyboard.md`

## Issues during this review

| Workflow point | What went wrong | Effect | Recovery or current state |
| --- | --- | --- | --- |
| Saving the research record | Git could not create `.git/index.lock` because repository metadata is read-only in the current workspace. | The scoped commit of the two research notes did not complete; the files remain in the working tree. | Used the authorized elevated write path; the scoped commit of both research notes completed. |
| Source assimilation research | Looked for a harness-local plugin README that is not present at that path. | No source evidence was lost; the lookup did not find the Thermos package description. | Read the README from the installed Thermos source package and inspected the copied harness skills, agents, and license instead. |
