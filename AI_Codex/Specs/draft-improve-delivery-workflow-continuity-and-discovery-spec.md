---
type: spec
work_item_type: Epic
ticket: null
area: delivery-workflow
stack: [python, markdown]
tags: [spec, epic]
created: 2026-09-23
source: [manual]
---

# Improve delivery workflow continuity and discovery — Epic Spec

## Problem / opportunity

The delivery harness can begin a new Story from approved backlog records and can resume tracker
enforcement after an intentional pause. It cannot yet assess implementation that already exists on
a branch before continuing work. It also turns an idea directly into backlog drafting without a
structured record for comparing product directions. Its worker support also lacks predefined roles
that match a bounded assignment to a model tier, reasoning effort, quota budget, and verification
contract.

## Objectives (draft)

- Allow a team to continue an existing implementation from a verified, human-approved assessment.
- Allow a team to select a product direction before the selected direction enters backlog drafting.
- Allow the harness to delegate bounded work through role-defined worker profiles while retaining
  root-agent control of approval-sensitive actions and final verification.

## Scope (draft)

### Included

- A workflow that assesses an existing branch, planned Tasks, evidence, and scope differences.
- A workflow that records candidate product directions and hands a selected direction to backlog
  drafting.
- Role-defined worker profiles and quota-aware delegation for bounded delivery work.

### Excluded

- Changes to the existing implementation, review, pull-request, or approval workflows.
- Automatic selection of a product direction or automatic completion of existing Tasks.
- Autonomous approval-sensitive tracker, source-control, or policy writes by a worker agent.

## Tech stack

The existing Python workflow runtime, local Markdown artifacts, Git evidence, and configured
tracker and source-control adapters.

## Research summary

No external library research is required. The scope is defined by the current local workflow,
artifact, and evidence contracts.

## References

- `docs/02-design/workflows.md`
- `docs/01-architecture/data-model.md`
- `plugins/monolithic-dev-harness/skills/implement-story/SKILL.md`
- `plugins/monolithic-dev-harness/skills/resume-tracker/SKILL.md`
- `plugins/monolithic-dev-harness/scripts/orchestrator/worker.py`

## Open questions

- What durable artifact format should hold a discovery record and a continuation assessment?
- Which role approves a continuation plan and a selected product direction?
- Which worker profiles and quota budgets should be enabled for the first release?

## Original description

"now document all the gaps from the answers"

"generate the nacklog directly, place it under AI_Codex"
