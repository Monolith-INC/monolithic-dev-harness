---
type: feature-spec
project: monolithic-dev-harness
date: 2026-10-02
status: approved
source: [stage-zero-redesign-bmad-analysis.md]
---

# Technical-first planning for assigned work

## Problem

The harness's first planning step is oriented around defining an idea and producing a product
specification. Developers more often receive a ticket or product-owner request for a change to an
existing product. That request may describe the desired outcome without establishing its behavior,
technical fit, risks, or implementation path.

When this kind of request goes straight to backlog drafting, the team can create work items before
checking the codebase, feasibility, dependencies, or scope. The detailed technical specification
then arrives later, after those decisions could have changed the work.

## Goal

Make the default first planning path for assigned work turn an incomplete request into a
repository-grounded, reviewable feature implementation strategy. The developer should understand
what is known, what still needs a product decision, how the change fits the existing system, which
approach is recommended, and what work and checks would follow approval.

Product ideation remains an optional path when the user wants to explore what to build. It is not a
required step for an assigned ticket.

## Users and entry point

- **Primary user:** a developer who has been assigned a ticket or received a draft feature request.
- **Supporting participants:** the product owner, tech lead, and other people who own unresolved
  product or engineering constraints.
- **Starting material:** an existing tracker item, a draft request, or an approved product intent.
  The request is an input to investigate, not proof that the feature is feasible or complete.

The flow must be able to read an existing ticket and its relevant context without starting
implementation or changing tracker state.

## Expected workflow

1. **Resume or open the request.** Find existing analysis for this work when possible. Record which
   ticket revision or request is being assessed.
2. **Read its context.** Inspect related work, repository guidance, product and design documents,
   architecture decisions, relevant code, and existing tests.
3. **Choose the appropriate route.** A coherent assigned change enters technical investigation.
   Split or route broader work according to the source workflow. Use product discovery only when the
   user asks to explore the problem or the intended outcome cannot yet be identified.
4. **Investigate the system.** Trace the relevant code, data, interfaces, dependencies, user flows,
   error behavior, and tests. Consult current authoritative documentation when an external technical
   fact could change the recommendation.
5. **Resolve discoverable questions.** Use repository and source evidence first. Separate facts,
   assumptions, product decisions, and engineering recommendations. Ask the user only for decisions
   that cannot be established from available evidence.
6. **Compare feasible approaches.** Explain affected parts, reuse, dependencies, data or interface
   changes, trade-offs, risks, and supporting evidence. Recommend an approach without hiding
   meaningful alternatives.
7. **Prepare and review the strategy.** Present a complete proposal for human review before writing
   tracker work or changing product code.
8. **Hand off after approval.** Create or update backlog work from the accepted proposal. Preserve
   its decisions so later story-level planning does not repeat discovery or silently change scope.

The route should be proportional to the work. A small, clear change should not receive unnecessary
artifacts; a broad or risky change may need product, experience, architecture, or multi-story
planning artifacts.

## Strategy contents

The smallest sufficient review package should state:

- requested outcome, scope, non-goals, constraints, and success checks;
- repository code map: relevant paths and symbols, patterns to reuse, and boundaries to preserve;
- recommended approach and material alternatives, with reasons and evidence;
- affected components, data, interfaces, dependencies, and migration or compatibility needs;
- risks, edge cases, assumptions, and unresolved owner decisions;
- ordered implementation slices, dependencies, and verification plan;
- links to supporting product, experience, or architecture decisions when they are needed.

## Source assimilation

Use BMad as the source method, following the harness's Thermos assimilation pattern. Bring in the
relevant open-source BMad workflow package and its required supporting files, preserve its license
and attribution, and adapt only the connections needed for harness hosts, tracker access, approvals,
and durable state. Do not create a parallel planning skill from scratch.

The initial source candidate is BMad `bmad-build`, especially its clarify-and-route and plan steps.
Assess `bmad-ticket`, `bmad-spec`, and `bmad-architecture` as related source components for larger
work and decisions that require them. The existing harness skill inventory is a reuse map, not a
limit on what can be assimilated. Keep BMad's product-discovery route available as an optional
choice.

## Acceptance criteria

- An assigned, underdeveloped request enters technical discovery by default rather than product
  ideation.
- Intake reads the request and relevant context without changing the source ticket or starting
  implementation.
- The investigation uses the actual repository and records evidence, reusable patterns, affected
  areas, risks, and unknowns.
- Repository-answerable questions are investigated before the user is asked to answer them.
- The proposal distinguishes facts and assumptions from product-owner decisions and engineering
  recommendations.
- The proposal compares feasible choices and includes a recommendation, implementation slices, and
  verification approach proportionate to the work.
- The user reviews the proposal before tracker publication or code changes.
- After approval, backlog and later story planning use the accepted proposal without repeating or
  silently changing its decisions.
- Users can explicitly choose product ideation when they want help discovering what to build.
- Imported workflow material retains source attribution and required license information, and
  harness-specific changes remain traceable to their source.

## Out of scope

- Replacing BMad's workflow with a newly invented planning framework.
- Making brainstorming or idea-forging mandatory for ticket work.
- Publishing tracker items or changing code before the user approves the strategy.
- Choosing a concrete Stage 0 skill name, artifact file location, or tracker schema before the source
  package and integration needs have been mapped.
- Resuming the paused live trial as part of this documentation work.

## Open design decisions

- Which request qualities allow a ticket to skip the full investigation and use a shorter path?
- Which BMad supporting runtime, templates, configuration, and method assets must be imported with
  `bmad-build` for faithful operation?
- Where should the approved feature strategy live, and how should it be referenced from local and
  remote tracker items?
- Which existing harness approval gates can protect strategy review and subsequent tracker writes?
- How should one-session work avoid duplicate planning while multi-story work retains feature-level
  decisions and story-level details?
- Which bounded experiments can run during discovery, and when is separate approval needed?

## Source references

- [BMad workflow analysis](../Artifacts/stage-zero-redesign-bmad-analysis.md)
- BMad `bmad-build`: `/mnt/DATA/Projects/Corporate/BMAD-METHOD/skills/bmad-build/`
- BMad planning guide: `/mnt/DATA/Projects/Corporate/BMAD-METHOD/docs/plan/choose-a-planning-path.md`
- Harness workflow today: `../../docs/02-design/workflows.md`
- Thermos assimilation reference: `../../plugins/monolithic-dev-harness/skills/thermos/SKILL.md`
