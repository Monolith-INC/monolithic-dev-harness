---
date: 2026-09-23
type: ticket
work_item_type: Feature
provider: local
parent_id: "pending:draft-improve-delivery-workflow-continuity-and-discovery"
language: en
tags: [ticket, feature, worker-agents, delivery-workflow]
---

# Enable role-defined worker-agent orchestration across delivery work

## Objective

Allow the harness to delegate bounded work to predefined worker roles whose model tier, reasoning
effort, quota budget, permitted tools, and verification contract match the assignment.

## Scope

### Included

- Versioned worker profiles for approved delivery roles.
- Deterministic profile selection, quota-aware delegation, and artifact-based result verification.

### Excluded

- Worker ownership of approval-sensitive tracker, source-control, or policy writes.
- Trusting a worker summary as completion evidence.

## Success Criteria

- [ ] Each delegated assignment uses a recorded worker profile and bounded input/output contract.
- [ ] The root agent verifies the output artifact before it accepts delegated work.

## Areas / modules involved

- `plugins/monolithic-dev-harness/scripts/orchestrator/`
- `plugins/monolithic-dev-harness/agents/`
- `plugins/monolithic-dev-harness/skills/`

## Original Description

"The lack of a worker-agent workflow with pre-defined agents having model tier and reasoning
strength set to match their work is a gap. Such protocol would reduce quota usage and provide a
more structured work discipline."
