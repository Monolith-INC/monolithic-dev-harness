# First planning step: technical discovery review

Date: 2026-10-02
Status: research and proposed direction; no harness implementation authorized by this note

> This was an initial proposal. The source-based workflow mapping and revised Stage 0 design are in [stage-zero-redesign-bmad-analysis.md](stage-zero-redesign-bmad-analysis.md).

## User direction

The main first planning step should serve a developer who brings a rough technical proposition or product-owner feature request. It should inspect the existing product and code, expose implementation risks and unknowns, compare feasible approaches with costs and benefits, and produce the documentation and complete implementation strategy needed to take the feature into delivery. Open-ended product ideation remains useful as an optional path when the user asks to explore what problem or product to pursue; it is not the main flow.

## What BMad actually does

- `bmad-brainstorming` is divergent idea generation. It is explicitly designed to generate many possible ideas and defer evaluation; it is not a technical implementation investigation.
- `bmad-forge-idea` pressure-tests an idea through questioning and perspectives. Its aim is stronger thinking or rejection, not a technical design or a commitment to build.
- `bmad-prd` captures product intent, users, capabilities, outcomes, and requirements. Its technical details are moved to an addendum or a later design step; a PRD is not an implementation plan.
- `bmad-spec` condenses intent into a WHAT contract: Why, capabilities, constraints, non-goals, and success signal. It specifically keeps implementation prescription in companions and does not perform discovery when input is too thin.
- `bmad-architecture` produces a short architecture spine. It fixes only non-obvious decisions that separately built units could otherwise make inconsistently. It is not an exhaustive design for one feature.
- The technical investigation closest to the user’s goal is later in `bmad-build`: Step 1 resolves the request and loads relevant evidence; Step 2 investigates the real codebase and produces an implementation plan with a code map, reused patterns, files, open questions, and review. The BMad guide places this after requirements and work items.

Therefore, the user’s description of brainstorming as a deep technical first step is not what the assimilated brainstorming skill does. BMad has the requested technical work, but it is split across architecture and build planning and currently occurs later in the process.

## What the harness currently does

`plugins/monolithic-dev-harness/skills/plan-initiative/SKILL.md` routes Stage 0 through optional product discovery and ends at a product `product-spec`. `harness/SKILL.md` then routes into backlog creation. Detailed story-local technical specifications are created later by `write-spec`, after work items and implementation tasks exist. `architecture-spine` can record cross-unit rules before backlog work, but its own scope excludes task-level technical designs.

The current Daybook live trial selected `brainstorm-ideas` because the sample request was an unresolved product opportunity and the user chose “Ideate for me.” That exercised ideation as the primary flow, which was the mismatch; the user clarified that ideation itself is still valuable as an optional path. It did not exercise the main technical-first path. The user chose to retain optional ideation; existing draft `AI_Codex/Tickets/Ready/draft-support-structured-product-discovery.md` already covers optional discovery and should be refined to distinguish it from the default technical-first route rather than duplicated. The trial is paused before any feature selection, backlog write, or code change.

The observed ideation run produced 36 ideas and stopped to ask the user to select one. The source BMad skill says to aim past 100 ideas and avoid stopping until the topic is spent. This is a workflow fidelity gap to preserve as a trial finding; the current harness adaptation only says “well beyond the first obvious batch,” so the source behavior was not carried over explicitly.

## Proposed Stage 0 behavior

1. Read the request, repository, existing product documentation, and recorded decisions. Separate facts, user requirements, and assumptions.
2. Classify the starting point. A draft requirement for a known product goes to technical discovery by default. An explicit request to find a problem or generate product directions may use optional product ideation. Clear, low-risk work can use a short path.
3. Investigate the affected code and its conventions. Identify relevant components, dependencies, data flow, interfaces, test coverage, and constraints. Check current authoritative documentation where a library, platform, or protocol detail could change the design.
4. Identify gaps and failure cases. Resolve facts from the repository or research first; ask the user only for product decisions or constraints that cannot be discovered. Keep unsupported assumptions visible.
5. Compare realistic implementation approaches. For each, explain behavior, affected areas, advantages, costs, risks, and what evidence supports the choice. Recommend one while leaving user-owned product choices open. Use a bounded prototype or experiment when research alone cannot settle a technical risk.
6. Produce a reviewable feature proposal: intended behavior and boundaries, technical design, rejected alternatives and reasons, risks and open questions, implementation slices, and verification strategy. Keep product intent separate from technical decisions.
7. Challenge the proposal with concrete failure scenarios and a simpler alternative. Present the proposal and critique together for one material user decision. Only after that decision should the workflow draft tracker work items.

Product ideation remains an explicit alternative route, not a mandatory preliminary step. A later user can choose to explore and validate the problem before technical discovery.

## Design cautions

- Do not move every implementation detail into a global architecture document. Use a feature-level technical proposal for a single feature; reserve architecture spines for decisions shared across independently built work.
- Do not treat an invented user scenario as evidence of demand. Keep product validation and technical feasibility distinct.
- Do not make the full technical spec wait until after task decomposition if its findings could change scope or feasibility. At the same time, avoid writing a detailed plan before enough product behavior is known. The route should allow a short intent clarification, technical investigation, then a bounded proposal before backlog drafting.
- Do not blindly copy BMad’s ceremonies. Adapt its useful codebase investigation, assumption marking, trade-off review, and durable decision history to the harness’s own interfaces and artifacts.

## Sources checked

- `plugins/monolithic-dev-harness/skills/plan-initiative/SKILL.md`
- `plugins/monolithic-dev-harness/skills/harness/SKILL.md`
- `plugins/monolithic-dev-harness/skills/architecture-spine/SKILL.md`
- `plugins/monolithic-dev-harness/skills/product-spec/SKILL.md`
- `plugins/monolithic-dev-harness/skills/write-spec/SKILL.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-brainstorming/SKILL.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-forge-idea/SKILL.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-prd/SKILL.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-spec/SKILL.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-architecture/SKILL.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-build/step-01-clarify-and-route.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-build/step-02-plan.md`
- `/mnt/DATA/Projects/Corporate/BMAD-METHOD/docs/plan/design-ux-and-architecture.md`
